"""A small HTTP API over the resolved guest data.

    uvicorn guestgraph.api:app --reload      (after `guestgraph demo` has built data/)
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from .activation import CONNECTORS
from .warehouse import SEGMENTS, build, segment_members, summary


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    data_dir = Path(data_dir or os.environ.get("GUESTGRAPH_DATA", "data"))
    con, res = build(data_dir / "loyalty_members.csv", data_dir / "transactions.csv")
    app = FastAPI(title="guestgraph", version="0.1.0",
                  description="Resolved guests, audiences and activation for restaurant data")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/summary")
    def get_summary():
        return summary(con, res)

    @app.get("/guests/{guest_id}")
    def get_guest(guest_id: str):
        row = con.execute("SELECT * FROM guest_profiles WHERE guest_id = ?", [guest_id]).fetchone()
        if not row:
            raise HTTPException(404, "guest not found")
        cols = [d[0] for d in con.description]
        return {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in zip(cols, row)}

    @app.get("/segments")
    def list_segments():
        return {s: summary(con, res)["segments"][s] for s in SEGMENTS}

    @app.post("/segments/{segment}/activate")
    def activate(segment: str, platform: str = Query("meta", enum=list(CONNECTORS)),
                 audience_id: str = "demo-audience", dry_run: bool = True):
        if segment not in SEGMENTS:
            raise HTTPException(404, f"unknown segment; choose from {SEGMENTS}")
        if not dry_run:
            raise HTTPException(400, "live uploads are disabled in the demo API")
        connector = CONNECTORS[platform](audience_id, dry_run=True)
        result = connector.upload(segment_members(con, segment))
        return result.__dict__

    return app


app = create_app() if Path(os.environ.get("GUESTGRAPH_DATA", "data"), "transactions.csv").exists() else FastAPI(
    title="guestgraph (no data yet: run `guestgraph demo` first)")
