import json
import time
from urllib.parse import parse_qs, urlparse


def test_kickoff_via_payment_test(client):
    r = client.post(
        "/events/payment/test",
        json={
            "order_id": "T1",
            "email": "demo@example.com",
            "name": "Demo",
            "skus": ["DPP-ESPR"],
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert "intake_url" in j
    assert "continuation_url" in j


def test_inquiry_submit_kickoff(anon_client):
    r = anon_client.post(
        "/api/inquiry/submit",
        data={
            "name": "Test User",
            "email": "inquiry@example.com",
            "subject": "CMMC L1",
            "message": "Need help with readiness.",
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert "project_id" in j
    assert "intake_url" in j
    assert "continuation_url" in j


def test_customer_launch_inquiry_to_intake(anon_client, client):
    """Inquiry → project → intake submit marks workflow step."""
    unique = str(int(time.time() * 1000))
    r = anon_client.post(
        "/api/inquiry/submit",
        data={
            "name": "Launch User",
            "email": f"launch-{unique}@example.com",
            "subject": "CMMC-L1",
            "message": "Customer launch path test.",
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("continuation_url")
    pid = j["project_id"]
    token = parse_qs(urlparse(j["intake_url"]).query)["token"][0]
    sub = anon_client.post(
        "/api/intake/submit",
        data={"token": token, "company": "Acme", "contact": "Launch User", "notes": "test"},
    )
    assert sub.status_code == 200
    assert sub.json()["ok"] is True
    st = client.get(f"/api/project/{pid}/status").json()["status"]
    intake_step = next((s for s in st["steps"] if s["id"] == "intake_received"), None)
    assert intake_step is not None, st.get("steps")
    assert intake_step["status"] == "done"
