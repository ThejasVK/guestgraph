"""Meta (Facebook/Instagram) Custom Audiences: POST /{audience_id}/users.

Meta expects SHA-256 of the normalized value. Phone numbers are digits only, including the
country code, with no plus sign. Large uploads are split into batches that share a session
so Meta can tell when the last one has arrived.
"""

from __future__ import annotations

from .base import Connector


class MetaCustomAudience(Connector):
    platform = "meta"
    api_version = "v21.0"

    def default_base_url(self) -> str:
        return "https://graph.facebook.com"

    def row(self, guest: dict):
        email, phone = guest.get("email_sha256"), guest.get("phone_sha256")
        if not (email or phone):
            return None
        return [email or "", phone or ""]

    def request(self, rows, batch_no, total_batches, session_id):
        body = {
            "session": {
                "session_id": int(session_id[:12], 16),
                "batch_seq": batch_no,
                "last_batch_flag": batch_no == total_batches,
            },
            "payload": {"schema": ["EMAIL", "PHONE"], "data": rows},
        }
        return f"/{self.api_version}/{self.audience_id}/users", body
