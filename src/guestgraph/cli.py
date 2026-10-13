"""Command line entry point.

    guestgraph demo          generate synthetic data and run the whole pipeline
    guestgraph run DATA_DIR  run the pipeline on your own CSVs
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .activation import CONNECTORS
from .evaluate import evaluate
from .generate import generate
from .measure import lift, required_n_per_group, simulate_outcomes
from .warehouse import SEGMENTS, build, segment_members, summary


def run(data_dir: Path, out_dir: Path) -> dict:
    con, res = build(data_dir / "loyalty_members.csv", data_dir / "transactions.csv",
                     db_path=out_dir / "guestgraph.duckdb")
    report = summary(con, res)
    if (data_dir / "_truth.csv").exists():
        report["resolution_quality"] = evaluate(res.txn_to_guest, data_dir / "_truth.csv")

    for seg in SEGMENTS:
        con.execute(f"COPY (SELECT p.* FROM seg_{seg} s JOIN guest_profiles p USING (guest_id)) "
                    f"TO '{(out_dir / f'segment_{seg}.csv').as_posix()}' (HEADER)")

    target = "lapsed_regulars"
    audience = segment_members(con, target)
    report["activation"] = {}
    for name, cls in CONNECTORS.items():
        r = cls(f"demo_{target}", dry_run=True, out_dir=out_dir / "payloads").upload(audience)
        report["activation"][name] = {"sent": r.sent, "skipped": r.skipped, "batches": r.batches}

    outcomes = simulate_outcomes([g["guest_id"] for g in audience], campaign=target)
    lr = lift(target, outcomes)
    report["measurement"] = lr.text()
    need = required_n_per_group(0.30, 0.25)
    if min(lr.exposed, lr.holdout) < need:
        report["measurement"] += (f". Too small to call: spotting a 25% lift needs about {need:,} guests "
                                  f"per group, so run it across more stores or a longer window")
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="guestgraph")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="generate synthetic data and run everything")
    d.add_argument("--data", default="data")
    d.add_argument("--out", default="out")
    d.add_argument("--guests", type=int, default=1500)
    r = sub.add_parser("run", help="run on existing CSVs")
    r.add_argument("data")
    r.add_argument("--out", default="out")
    a = ap.parse_args(argv)

    data, out = Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "demo":
        generate(data, n_people=a.guests)
    rep = run(data, out)

    print(f"Transactions: {rep['transactions']:,}  resolved to a guest: {rep['resolution_rate']:.0%}")
    print(f"Guests: {rep['guests']:,}  loyalty members: {rep['loyalty_members_seen']:,}  "
          f"non-loyalty but reachable: {rep['non_loyalty_but_reachable']:,}")
    print(f"Shared cards blocked from linking: {rep['blocked_shared_cards']}")
    if "resolution_quality" in rep:
        q = rep["resolution_quality"]
        print(f"Against ground truth: {q['real_people']:,} real people -> {q['guests']:,} guest IDs; "
              f"purity {q['purity']:.1%} (no strangers merged), "
              f"{q['avg_guest_ids_per_person']:.2f} IDs per person")
    for s, v in rep["segments"].items():
        print(f"  segment {s:<22} {v['size']:>5} guests, {v['reachable']:>5} reachable")
    for p, v in rep["activation"].items():
        print(f"  {p:<7} dry-run upload: {v['sent']} rows in {v['batches']} batch(es), {v['skipped']} skipped")
    print(rep["measurement"])
    print(f"Wrote {out}/report.json, segment CSVs and payloads/")


if __name__ == "__main__":
    main()
