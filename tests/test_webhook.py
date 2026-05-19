import json
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)


def test_kickoff_via_payment_test():
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


def test_inquiry_submit_kickoff():
    r = client.post(
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
