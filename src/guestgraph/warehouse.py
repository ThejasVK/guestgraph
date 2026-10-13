"""Load data into DuckDB, run identity resolution, build profiles and segments.

DuckDB stands in for the warehouse locally (no account, no cost). The SQL is kept close to
Snowflake's dialect; see README "Porting to Snowflake".
"""

from __future__ import annotations

import csv
from importlib import resources
from pathlib import Path

import duckdb

from .resolve import Resolution, resolve

SEGMENTS = ["lapsed_regulars", "high_value", "non_loyalty_regulars", "new_guests"]


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return [{k: (v if v != "" else None) for k, v in row.items()} for row in csv.DictReader(f)]


def _sql(name: str) -> str:
    return resources.files("guestgraph").joinpath("sql", name).read_text()


def build(members_csv: Path, transactions_csv: Path, db_path: str | Path = ":memory:") -> tuple[duckdb.DuckDBPyConnection, Resolution]:
    members = _read_csv(Path(members_csv))
    txns = _read_csv(Path(transactions_csv))
    res = resolve(members, txns)

    con = duckdb.connect(str(db_path))
    con.execute(f"""
        CREATE OR REPLACE TABLE transactions AS
        SELECT txn_id, store_id, CAST(txn_date AS DATE) AS txn_date, CAST(amount AS DOUBLE) AS amount,
               NULLIF(card_token, '') AS card_token, NULLIF(member_id, '') AS member_id
        FROM read_csv_auto('{Path(transactions_csv).as_posix()}', all_varchar=true)
    """)
    con.execute("CREATE OR REPLACE TABLE txn_guest (txn_id VARCHAR, guest_id VARCHAR)")
    con.executemany("INSERT INTO txn_guest VALUES (?, ?)", list(res.txn_to_guest.items()))

    con.execute("""CREATE OR REPLACE TABLE guest_identity (
        guest_id VARCHAR PRIMARY KEY, is_member BOOLEAN, has_email BOOLEAN, has_phone BOOLEAN,
        email_sha256 VARCHAR, phone_sha256 VARCHAR, phone_e164_sha256 VARCHAR, member_ids VARCHAR)""")
    rows = []
    for gid, g in res.guest_identifiers.items():
        first = lambda s: sorted(s)[0] if s else None  # noqa: E731  one identifier per type is enough to match
        rows.append((gid, bool(g["member_ids"]), bool(g["email_sha256"]), bool(g["phone_sha256"]),
                     first(g["email_sha256"]), first(g["phone_sha256"]), first(g["phone_e164_sha256"]),
                     ",".join(sorted(g["member_ids"])) or None))
    con.executemany("INSERT INTO guest_identity VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)

    con.execute(_sql("profiles.sql"))
    con.execute(_sql("segments.sql"))
    return con, res


def segment_members(con: duckdb.DuckDBPyConnection, segment: str, reachable_only: bool = True) -> list[dict]:
    if segment not in SEGMENTS:
        raise KeyError(f"unknown segment {segment!r}; choose from {SEGMENTS}")
    q = f"""
        SELECT i.guest_id, i.email_sha256, i.phone_sha256, i.phone_e164_sha256
        FROM seg_{segment} s JOIN guest_identity i USING (guest_id)
        {"WHERE i.has_email OR i.has_phone" if reachable_only else ""}
        ORDER BY i.guest_id
    """
    cols = ["guest_id", "email_sha256", "phone_sha256", "phone_e164_sha256"]
    return [dict(zip(cols, r)) for r in con.execute(q).fetchall()]


def summary(con: duckdb.DuckDBPyConnection, res: Resolution) -> dict:
    tx_total, tx_resolved = con.execute(
        "SELECT COUNT(*), COUNT(g.guest_id) FROM transactions t JOIN txn_guest g USING (txn_id)").fetchone()
    members, non_members_reachable = con.execute(
        "SELECT SUM(is_member::INT), SUM(CASE WHEN NOT is_member AND reachable THEN 1 ELSE 0 END) FROM guest_profiles").fetchone()
    out = {
        "transactions": tx_total,
        "transactions_resolved": tx_resolved,
        "resolution_rate": round(tx_resolved / tx_total, 3) if tx_total else 0,
        "guests": con.execute("SELECT COUNT(*) FROM guest_profiles").fetchone()[0],
        "loyalty_members_seen": int(members or 0),
        "non_loyalty_but_reachable": int(non_members_reachable or 0),
        "blocked_shared_cards": len(res.blocked_cards),
        "segments": {},
    }
    for s in SEGMENTS:
        total = con.execute(f"SELECT COUNT(*) FROM seg_{s}").fetchone()[0]
        out["segments"][s] = {"size": total, "reachable": len(segment_members(con, s))}
    return out
