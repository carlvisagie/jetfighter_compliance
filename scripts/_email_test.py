"""
KYC SEV-1 — Live email test + pipeline audit.
Sends ONE real email via the production endpoint.
"""
import httpx, json, sys
from datetime import datetime

BASE = "https://jetfighter-compliance.onrender.com"
PWD  = "IZAKviss!@34"
TEST_EMAIL = "carlvisagie@gmail.com"  # operator's own address

def login():
    r = httpx.post(f"{BASE}/api/ops/login", json={"password": PWD}, timeout=15)
    assert r.status_code == 200
    return dict(r.cookies)

cookies = login()
print(f"[OK] Authenticated\n")

# ── LIVE EMAIL TEST ────────────────────────────────────────────
print("="*55)
print("  LIVE EMAIL TEST")
print("="*55)

# Try the operator alert endpoint — it sends a real email
resp = httpx.post(
    f"{BASE}/api/operator/test-email",
    json={
        "to": TEST_EMAIL,
        "subject": "KYC SEV-1 Organism Email Test",
        "body": "This is a live production email test from the KYC organism. If received, the email pipeline is operational.",
    },
    cookies=cookies,
    timeout=30,
)
print(f"  /api/operator/test-email -> {resp.status_code}")
if resp.status_code in (200, 201):
    r = resp.json()
    print(f"  provider_attempted:      {r.get('provider_attempted') or r.get('provider')}")
    print(f"  provider_succeeded:      {r.get('provider_succeeded') or r.get('success')}")
    print(f"  email_sent:              {r.get('email_sent') or r.get('sent')}")
    print(f"  resend_message_id:       {r.get('resend_message_id') or r.get('message_id')}")
    print(f"  fallback_used:           {r.get('fallback_used')}")
    print(f"  delivery_record_written: {r.get('delivery_record_written')}")
    print(f"  delivery_record_path:    {r.get('delivery_record_path')}")
    print(f"  full response: {json.dumps(r, indent=2)}")
else:
    print(f"  response: {resp.text[:500]}")

    # Try alternate endpoints
    print("\n  Trying /api/operator/send-test-email ...")
    resp2 = httpx.post(
        f"{BASE}/api/operator/send-test-email",
        json={"to": TEST_EMAIL},
        cookies=cookies,
        timeout=30,
    )
    print(f"  -> {resp2.status_code}: {resp2.text[:300]}")

    print("\n  Trying /api/ops/test-email ...")
    resp3 = httpx.post(
        f"{BASE}/api/ops/test-email",
        json={"to": TEST_EMAIL, "subject": "KYC Organism Email Test"},
        cookies=cookies,
        timeout=30,
    )
    print(f"  -> {resp3.status_code}: {resp3.text[:300]}")
