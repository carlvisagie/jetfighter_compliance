import httpx

BASE = "https://jetfighter-compliance.onrender.com"
r = httpx.post(f"{BASE}/api/ops/login", json={"password": "IZAKviss!@34"}, timeout=15)
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
