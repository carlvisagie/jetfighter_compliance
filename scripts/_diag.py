import httpx, json

BASE = "https://jetfighter-compliance.onrender.com"
r = httpx.post(f"{BASE}/api/ops/login", json={"password": "IZAKviss!@34"}, timeout=15)
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
