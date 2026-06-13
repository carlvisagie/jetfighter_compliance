"""Final production health check - verify all critical systems work."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("FINAL PRODUCTION HEALTH CHECK")
print("=" * 80)

endpoints = [
    "/api/cognitive-topology",
    "/api/operator/acquisition-intelligence",
    "/api/operator/reddit-acquisition",
    "/api/operator/compliance-intelligence",
    "/api/operator/organism-observability",
    "/api/operator/operational-alerts",
    "/api/operator/customer-friction",
    "/api/operator/evidence-intelligence/status",
]

passed = 0
failed = 0

for endpoint in endpoints:
    try:
        r = client.get(f"{base_url}{endpoint}", timeout=20)
        if r.status_code == 200:
            data = r.json()
            if data.get('ok', True):
                print(f"[OK] {endpoint}")
                passed += 1
            else:
                print(f"[WARN] {endpoint}: ok=false - {data.get('error', '')}")
                failed += 1
        else:
            print(f"[FAIL] {endpoint}: HTTP {r.status_code}")
            failed += 1
    except Exception as e:
        print(f"[ERROR] {endpoint}: {str(e)[:50]}")
        failed += 1

print("\n" + "=" * 80)
print(f"PASSED: {passed}/{len(endpoints)}")
print(f"FAILED: {failed}/{len(endpoints)}")
print("=" * 80)

if failed == 0:
    print("\n[SUCCESS] All critical endpoints are healthy!")
else:
    print(f"\n[WARNING] {failed} endpoints need attention")
