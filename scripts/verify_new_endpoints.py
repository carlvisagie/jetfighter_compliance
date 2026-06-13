"""Verify all newly created endpoints are working in production."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("VERIFYING NEWLY CREATED ENDPOINTS IN PRODUCTION")
print("=" * 80)

# All newly created endpoints
new_endpoints = [
    ("/api/operator/acquisition/pending", "GET", "Acquisition Pending Queue"),
    ("/api/operator/acquisition/reddit/queue", "GET", "Reddit Acquisition Queue"),
    ("/api/operator/vio/status", "GET", "VIO Status"),
    ("/api/operator/knowledge/status", "GET", "Knowledge Status"),
    ("/api/operator/evidence-intelligence/status", "GET", "Evidence Intelligence Status"),
    ("/api/operator/memory/integrity", "GET", "Memory Integrity"),
    ("/api/operator/learning/status", "GET", "Learning Status"),
    ("/api/test-webhook", "POST", "Test Webhook (POST)"),
]

print(f"\n[INFO] Checking {len(new_endpoints)} newly created endpoints...\n")

working = []
failed = []

for endpoint, method, name in new_endpoints:
    try:
        if method == "GET":
            r = client.get(f"{base_url}{endpoint}")
        else:  # POST
            r = client.post(f"{base_url}{endpoint}", json={"test": "payload"})
        
        status = r.status_code
        
        if status == 200:
            data = r.json()
            ok = data.get('ok', True)
            
            if ok:
                print(f"[OK] {name}")
                print(f"     {endpoint} -> {status}")
                working.append((name, endpoint))
            else:
                error = data.get('error', 'ok=false')
                print(f"[FAIL] {name}")
                print(f"       {endpoint} -> {status} (ok=false)")
                print(f"       Error: {error}")
                failed.append((name, endpoint, error))
        else:
            print(f"[FAIL] {name}")
            print(f"       {endpoint} -> {status}")
            body = r.text[:200] if r.text else "No response"
            failed.append((name, endpoint, f"HTTP {status}: {body}"))
            
    except Exception as e:
        print(f"[ERROR] {name}")
        print(f"        {endpoint}")
        print(f"        Exception: {e}")
        failed.append((name, endpoint, str(e)))

print("\n" + "=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)
print(f"\nWorking: {len(working)}/{len(new_endpoints)}")
print(f"Failed: {len(failed)}/{len(new_endpoints)}")

if failed:
    print("\n" + "=" * 80)
    print("FAILED ENDPOINTS")
    print("=" * 80)
    
    for name, endpoint, error in failed:
        print(f"\n{name}")
        print(f"  Endpoint: {endpoint}")
        print(f"  Error: {error}")
    
    print("\n[ACTION REQUIRED] Fix the failed endpoints above.")
else:
    print("\n[SUCCESS] All newly created endpoints are working in production!")

print("\n" + "=" * 80)
