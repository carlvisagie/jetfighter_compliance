"""Diagnostic script — loads OPS_PASSWORD from environment or .ops_env file."""
import httpx, json, os, sys

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

# Full diagnostics
r2 = httpx.get(f"{BASE}/api/operator/intake/diagnostics", cookies=cookies, timeout=20)
print("Diagnostics HTTP:", r2.status_code)
print(json.dumps(r2.json(), indent=2))

# Also check VIO overview directly
r3 = httpx.get(f"{BASE}/api/operator/vio/overview", cookies=cookies, timeout=20)
print("\nVIO overview HTTP:", r3.status_code)
d = r3.json()
print("Companies:", len(d.get("companies") or []))
print("Error:", d.get("error"))
