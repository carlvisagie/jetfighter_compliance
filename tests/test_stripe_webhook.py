import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from server import app
from services.config import SETTINGS
from services.stripe_hook import verify_stripe_signature

client = TestClient(app)


def _sign(payload: bytes, secret: str) -> str:
    ts = str(int(time.time()))
    signed = f"{ts}.{payload.decode()}".encode()
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_verify_stripe_signature_roundtrip():
    secret = "whsec_test_secret"
    body = b'{"type":"checkout.session.completed"}'
    header = _sign(body, secret)
    assert verify_stripe_signature(body, header, secret) is True


def test_stripe_webhook_kickoff(monkeypatch):
    secret = "whsec_test_secret"
    monkeypatch.setattr(SETTINGS, "stripe_webhook_secret", secret)
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "customer_details": {"email": "stripe@example.com", "name": "Stripe Buyer"},
                "metadata": {"sku": "CMMC-L1-FAST"},
            }
        },
    }
    body = json.dumps(event).encode()
    r = client.post(
        "/webhooks/stripe",
        data=body,
        headers={"Stripe-Signature": _sign(body, secret), "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert "intake_url" in j
    assert "upload_url" in j
