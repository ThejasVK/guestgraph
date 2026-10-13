"""Google Ads Customer Match via an OfflineUserDataJob.

The detail that bites people: Google hashes phone numbers in E.164 format *with* the plus
sign (sha256("+15512353720")), while Meta hashes digits only. Same guest, different hash.
That's why identity resolution keeps both phone hashes.
"""

from __future__ import annotations

from .base import Connector


class GoogleCustomerMatch(Connector):
    platform = "google"
    batch_size = 5_000  # stay well under the per-request operation cap

    def default_base_url(self) -> str:
        return "https://googleads.googleapis.com/v18"

    def row(self, guest: dict):
        ids = []
        if guest.get("email_sha256"):
            ids.append({"hashedEmail": guest["email_sha256"]})
        if guest.get("phone_e164_sha256"):
            ids.append({"hashedPhoneNumber": guest["phone_e164_sha256"]})
        if not ids:
            return None
        return {"create": {"userIdentifiers": ids}}

    def request(self, rows, batch_no, total_batches, session_id):
        # audience_id here is the offlineUserDataJobs resource name
        body = {"operations": rows, "enablePartialFailure": True}
        return f"/{self.audience_id}:addOperations", body
