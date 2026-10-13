import json

from guestgraph.cli import run
from guestgraph.warehouse import SEGMENTS, segment_members, summary


def test_profiles_and_segments(built):
    con, res = built
    rep = summary(con, res)
    assert rep["guests"] > 100
    assert 0.85 < rep["resolution_rate"] <= 1.0      # only cash-without-ID visits stay anonymous
    assert rep["non_loyalty_but_reachable"] >= 0
    for s in SEGMENTS:
        assert rep["segments"][s]["reachable"] <= rep["segments"][s]["size"]


def test_resolution_collapses_more_than_one_card_per_member(built):
    con, _ = built
    # some guests pay with two different cards; they should still be one guest
    multi = con.execute("""
        SELECT COUNT(*) FROM (
          SELECT g.guest_id FROM transactions t JOIN txn_guest g USING (txn_id)
          WHERE g.guest_id IS NOT NULL AND t.card_token IS NOT NULL
          GROUP BY g.guest_id HAVING COUNT(DISTINCT t.card_token) > 1)""").fetchone()[0]
    assert multi > 0


def test_reachable_members_have_hashes(built):
    con, _ = built
    for g in segment_members(con, "high_value"):
        assert g["email_sha256"] or g["phone_sha256"]
        assert "@" not in (g["email_sha256"] or "")      # never raw PII


def test_end_to_end_run_writes_outputs(data_dir, tmp_path):
    rep = run(data_dir, tmp_path)
    assert (tmp_path / "report.json").exists()
    assert json.loads((tmp_path / "report.json").read_text())["guests"] == rep["guests"]
    assert list((tmp_path / "payloads").glob("meta_*.json"))
    assert "returned" in rep["measurement"]


def test_resolution_quality_against_ground_truth(data_dir, built):
    from guestgraph.evaluate import evaluate
    _, res = built
    q = evaluate(res.txn_to_guest, data_dir / "_truth.csv")
    assert q["purity"] > 0.99            # strangers are (almost) never merged
    assert q["avg_guest_ids_per_person"] < 1.3
