"""
KYC — Live email test + pipeline audit.
Sends ONE real email via the production endpoint.
OPS_PASSWORD loaded from OPS_PASSWORD env var or .ops_env file.
"""
import httpx, json, os, sys
from datetime import datetime

def _load_password() -> str:
    pwd = os.getenv("OPS_PASSWORD", "")
    if not pwd:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".ops_env")
        try:
            for line in open(env_file):
                if line.startswith("OPS_PASSWORD="):
                    pwd = line.split("=", 1)[1].strip()
                    break
        except FileNotFoundError:
            pass
    if not pwd:
        sys.exit("ERROR: OPS_PASSWORD not set. Export it or add to .ops_env")
    return pwd

BASE = os.getenv("KYC_BASE_URL", "https://jetfighter-compliance.onrender.com")
TEST_EMAIL = os.getenv("TEST_EMAIL", "carlvisagie@gmail.com")

def login():
    r = httpx.post(f"{BASE}/api/ops/login", json={"password": _load_password()}, timeout=15)
    assert r.status_code == 200
    return dict(r.cookies)

cookies = login()
print(f"[OK] Authenticated\n")

# ── LIVE EMAIL TEST ────────────────────────────────────────────
print("="*55)
print("  LIVE EMAIL TEST")
print("="*55)

resp = httpx.post(
    f"{BASE}/api/operator/test-email",
    json={
        "to": TEST_EMAIL,
        "subject": "KYC Organism Email Test",
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
    print(f"  full response: {json.dumps(r, indent=2)}")
else:
    print(f"  response: {resp.text[:500]}")
