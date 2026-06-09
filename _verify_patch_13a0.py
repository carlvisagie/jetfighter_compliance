"""Verify PATCH 13A-0 in production."""
import sys
import json
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from lib.ops_client import authenticate_production

def main():
    print("=== PATCH 13A-0 PRODUCTION VERIFICATION ===\n")
    
    # Authenticate and get organism state
    client, _, diag = authenticate_production(verify_deploy=False)
    base_url = diag.base_url
    
    print(f"   Base URL: {base_url}")
    
    print("\n1. Fetching production organism state...")
    r = client.get(f"{base_url}/api/operator/organism/state")
    
    print(f"   Status: {r.status_code}")
    print(f"   Headers: {dict(r.headers)}")
    
    if r.status_code != 200:
        print(f"FAILED to fetch organism state: {r.status_code}")
        print(f"Response: {r.text[:500]}")
        return
    
    # Get SHA from headers
    prod_sha = r.headers.get("x-kyc-git-commit", "MISSING")
    print(f"   Production SHA: {prod_sha}")
    print(f"   Contains f6c10de: {'f6c10de' in prod_sha}")
    
    # Try to parse JSON
    try:
        data = r.json()
    except Exception as e:
        print(f"FAILED to parse JSON: {e}")
        print(f"Response text (first 500 chars): {r.text[:500]}")
        return
    health_state = data.get("health_state")
    checks = data.get("checks", [])
    
    print(f"\n2. Organism Health State: {health_state}")
    
    # Find compliance_health_coverage check
    print("\n3. Compliance Health Coverage Check:")
    ch_check = next((c for c in checks if c["name"] == "compliance_health_coverage"), None)
    
    if not ch_check:
        print("   [FAIL] compliance_health_coverage check NOT FOUND")
        return
    
    print("   [OK] compliance_health_coverage check exists")
    print(f"   Severity: {ch_check.get('severity')}")
    print(f"   OK: {ch_check.get('ok')}")
    print(f"   Detail: {ch_check.get('detail')}")
    
    evidence = ch_check.get("evidence", {})
    coverage = evidence.get("coverage_percent", -1)
    required_total = evidence.get("required_total", -1)
    unknown = evidence.get("unknown", -1)
    verified = evidence.get("verified", -1)
    
    print(f"\n4. Verification Values:")
    print(f"   Coverage: {coverage}%")
    print(f"   Required Total: {required_total}")
    print(f"   Unknown: {unknown}")
    print(f"   Verified: {verified}")
    
    # Verify expectations
    print("\n5. Expected Values Check:")
    checks_passed = []
    checks_failed = []
    
    if ch_check.get("severity") == "amber":
        checks_passed.append("[OK] Severity is AMBER (as expected)")
    else:
        checks_failed.append(f"[FAIL] Severity is {ch_check.get('severity')}, expected AMBER")
    
    if coverage == 0.0:
        checks_passed.append("[OK] Coverage is 0.0% (as expected)")
    else:
        checks_failed.append(f"[FAIL] Coverage is {coverage}%, expected 0.0%")
    
    if required_total == 9:
        checks_passed.append("[OK] Required total is 9 (as expected)")
    else:
        checks_failed.append(f"[FAIL] Required total is {required_total}, expected 9")
    
    if unknown == 9:
        checks_passed.append("[OK] Unknown is 9 (as expected)")
    else:
        checks_failed.append(f"[FAIL] Unknown is {unknown}, expected 9")
    
    if verified == 0:
        checks_passed.append("[OK] No fake PASS values (verified=0)")
    else:
        checks_failed.append(f"[FAIL] Fake passes detected: verified={verified}, expected 0")
    
    for check in checks_passed:
        print(f"   {check}")
    
    for check in checks_failed:
        print(f"   {check}")
    
    # Failed checks summary
    print("\n6. Failed Checks (non-INFO):")
    failed_checks = [c for c in checks if not c.get("ok")]
    for fc in failed_checks:
        print(f"   - {fc['name']}: {fc.get('severity')} - {fc.get('detail', '')[:80]}")
    
    # Final verdict
    print("\n=== VERDICT ===")
    if checks_failed:
        print("NO-GO: Verification failures detected")
        for fail in checks_failed:
            print(f"   {fail}")
    elif "f6c10de" not in prod_sha:
        print("NO-GO: Production SHA does not contain f6c10de")
    else:
        print("GO: All production checks passed")
        print("   - SHA verified")
        print("   - compliance_health_coverage check present")
        print("   - All values match expectations")
        print("   - No fake PASS values")
        print("\n   Ready for next patch.")

if __name__ == "__main__":
    main()
