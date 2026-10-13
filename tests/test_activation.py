import json

import httpx
import pytest

from guestgraph.activation import GoogleCustomerMatch, MetaCustomAudience
from guestgraph.normalize import sha256

GUESTS = [
    {"guest_id": "G1", "email_sha256": sha256("a@x.com"), "phone_sha256": sha256("15512353720"),
     "phone_e164_sha256": sha256("+15512353720")},
    {"guest_id": "G2", "email_sha256": None, "phone_sha256": None, "phone_e164_sha256": None},
]


def test_meta_payload_shape_and_skips_unreachable():
    m = MetaCustomAudience("123", dry_run=True)
    res = m.upload(GUESTS)
    assert (res.sent, res.skipped) == (1, 1)
    path, body = m.request([m.row(GUESTS[0])], 1, 1, "ab" * 16)
    assert path.endswith("/123/users")
    assert body["payload"]["schema"] == ["EMAIL", "PHONE"]
    assert body["session"]["last_batch_flag"] is True


def test_google_uses_e164_phone_hash_not_digits_only():
    g = GoogleCustomerMatch("customers/1/offlineUserDataJobs/2")
    ids = g.row(GUESTS[0])["create"]["userIdentifiers"]
    assert {"hashedPhoneNumber": sha256("+15512353720")} in ids
    assert {"hashedPhoneNumber": sha256("15512353720")} not in ids


def test_batches_split_and_last_flag(tmp_path):
    m = MetaCustomAudience("9", dry_run=True, out_dir=tmp_path)
    m.batch_size = 2
    many = [dict(GUESTS[0], guest_id=f"G{i}") for i in range(5)]
    res = m.upload(many)
    assert res.batches == 3
    last = json.loads((tmp_path / "meta_9_batch3.json").read_text())
    assert last["body"]["session"]["last_batch_flag"] is True


def test_live_upload_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"})
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"num_received": 1})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    m = MetaCustomAudience("123", access_token="tok", client=client, dry_run=False, sleep=lambda s: None)
    res = m.upload(GUESTS[:1])
    assert calls["n"] == 3
    assert res.responses == [{"num_received": 1}]


def test_live_upload_gives_up_after_max_retries():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    m = MetaCustomAudience("1", client=client, dry_run=False, max_retries=2, sleep=lambda s: None)
    with pytest.raises(httpx.HTTPStatusError):
        m.upload(GUESTS[:1])
