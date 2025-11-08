import json, hmac, hashlib, base64
from fastapi.testclient import TestClient
from server import app
from services.config import SETTINGS

client = TestClient(app)

def hmake(body: bytes) -> str:
    digest = hmac.new(SETTINGS.shopify_webhook_secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()

def test_shopify_webhook_hmac():
    payload = {"id":"12345","email":"x@y.com","customer":{"first_name":"A","last_name":"B"},
               "line_items":[{"sku":"CMMC-L1"}]}
    body = json.dumps(payload).encode()
    h = hmake(body)
    r = client.post("/webhooks/shopify/orders-paid", data=body, headers={"X-Shopify-Hmac-Sha256":h})
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert "intake_url" in j

def test_local_test_endpoint():
    r = client.post("/events/payment/test", json={
        "order_id":"T1","email":"demo@example.com","name":"Demo","skus":["DPP-ESPR"]
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
