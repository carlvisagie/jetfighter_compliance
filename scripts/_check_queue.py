"""Queue inspector — loads OPS_PASSWORD from environment or .ops_env file."""
import httpx, os, sys

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
r = httpx.post(f"{BASE}/api/ops/login", json={"password": _load_password()}, timeout=15)
cookies = dict(r.cookies)
print("Login:", r.status_code)

r2 = httpx.get(f"{BASE}/api/operator/intake/queue",
               params={"limit": 20, "include_archived": "true"},
               cookies=cookies, timeout=15)
data = r2.json()
print("Queue HTTP:", r2.status_code)
print("Queue depth:", data.get("queue_depth"))
print("Total rows:", len(data.get("queue") or []))
print("Empty reason:", data.get("queue_empty_reason"))
print("Diag dirs:", (data.get("diagnostics") or {}).get("intake_directories_found"))

for row in (data.get("queue") or []):
    print(f"  {row['intake_id']} | {row.get('company','')[:40]} | {row.get('review_status','')}")
