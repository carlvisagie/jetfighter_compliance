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


def test_customer_launch_inquiry_to_intake():
  """Inquiry → project → intake submit marks workflow step."""
  r = client.post(
    "/api/inquiry/submit",
    data={
      "name": "Launch User",
      "email": "launch@example.com",
      "subject": "CMMC-L1",
      "message": "Customer launch path test.",
    },
  )
  assert r.status_code == 200
  j = r.json()
  pid = j["project_id"]
  token = j["intake_url"].split("token=", 1)[1]
  sub = client.post(
    "/api/intake/submit",
    data={"token": token, "company": "Acme", "contact": "Launch User", "notes": "test"},
  )
  assert sub.status_code == 200
  assert sub.json()["ok"] is True
  st = client.get(f"/api/project/{pid}/status").json()["status"]
  intake_step = next(s for s in st["steps"] if s["id"] == "intake_received")
  assert intake_step["status"] == "done"
