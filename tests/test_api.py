from fastapi.testclient import TestClient

from guestgraph.api import create_app


def test_api(data_dir):
    c = TestClient(create_app(data_dir))
    assert c.get("/health").json() == {"ok": True}
    seg = c.get("/segments").json()
    assert "lapsed_regulars" in seg
    gid = c.post("/segments/high_value/activate?platform=google").json()
    assert gid["platform"] == "google" and gid["dry_run"] is True
    assert c.post("/segments/nope/activate").status_code == 404
    assert c.post("/segments/high_value/activate?dry_run=false").status_code == 400
    assert c.get("/guests/does-not-exist").status_code == 404
