"""Shared plumbing for pushing audiences to ad-platform APIs.

Partner APIs fail in predictable ways: rate limits (HTTP 429), transient 5xx errors,
payload size caps. Every connector gets the same batching, retry-with-backoff and dry-run
behaviour so each platform class only has to describe its own payload format.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

RETRYABLE = {429, 500, 502, 503, 504}


@dataclass
class ActivationResult:
    platform: str
    audience_id: str
    sent: int
    skipped: int
    batches: int
    dry_run: bool
    responses: list[dict] = field(default_factory=list)


class Connector:
    platform = "base"
    batch_size = 10_000

    def __init__(self, audience_id: str, *, access_token: str = "", base_url: str = "",
                 client: httpx.Client | None = None, dry_run: bool = True,
                 out_dir: Path | None = None, max_retries: int = 4,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.audience_id = audience_id
        self.access_token = access_token
        self.base_url = base_url.rstrip("/") or self.default_base_url()
        self.client = client
        self.dry_run = dry_run
        self.out_dir = out_dir
        self.max_retries = max_retries
        self.sleep = sleep

    # --- per-platform hooks -------------------------------------------------------------
    def default_base_url(self) -> str:
        raise NotImplementedError

    def row(self, guest: dict) -> object | None:
        """Turn one guest (hashed identifiers) into the platform's row format, or None to skip."""
        raise NotImplementedError

    def request(self, rows: list, batch_no: int, total_batches: int, session_id: str) -> tuple[str, dict]:
        """Return (url_path, json_body) for one batch."""
        raise NotImplementedError

    # --- shared behaviour ---------------------------------------------------------------
    def _post(self, path: str, body: dict) -> dict:
        assert self.client is not None, "a live upload needs an httpx.Client"
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            resp = self.client.post(f"{self.base_url}{path}", json=body, headers=headers, timeout=30)
            if resp.status_code not in RETRYABLE:
                resp.raise_for_status()
                return resp.json() if resp.content else {}
            if attempt == self.max_retries:
                resp.raise_for_status()
            retry_after = resp.headers.get("Retry-After")
            self.sleep(float(retry_after) if retry_after else delay)
            delay *= 2
        return {}

    def upload(self, guests: Iterable[dict]) -> ActivationResult:
        rows, skipped = [], 0
        for g in guests:
            r = self.row(g)
            if r is None:
                skipped += 1
            else:
                rows.append(r)
        batches = [rows[i:i + self.batch_size] for i in range(0, len(rows), self.batch_size)] or [[]]
        session_id = uuid.uuid4().hex
        result = ActivationResult(self.platform, self.audience_id, len(rows), skipped,
                                  len(batches), self.dry_run)
        for n, batch in enumerate(batches, start=1):
            path, body = self.request(batch, n, len(batches), session_id)
            if self.dry_run:
                if self.out_dir:
                    self.out_dir.mkdir(parents=True, exist_ok=True)
                    (self.out_dir / f"{self.platform}_{self.audience_id}_batch{n}.json").write_text(
                        json.dumps({"POST": path, "body": body}, indent=2))
                result.responses.append({"dry_run": True, "path": path, "rows": len(batch)})
            else:
                result.responses.append(self._post(path, body))
        return result
