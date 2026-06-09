"""Quick production check for PATCH 13A-0."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from lib.ops_client import authenticate_production
import json

try:
    client, _, diag = authenticate_production(verify_deploy=False)
    
    print("=== PRODUCTION CHECK ===")
    print(f"Base URL: {diag.base_url}")
    
    sha = diag.build_info.get("git_commit", "MISSING")
    print(f"SHA: {sha}")
    print(f"Contains f6c10de: {'YES' if 'f6c10de' in sha else 'NO'}")
    
    r = client.get(f"{diag.base_url}/api/operator/organism/state")
    data = r.json()
    
    checks = data.get("checks", [])
    ch = next((c for c in checks if c["name"] == "compliance_health_coverage"), None)
    
    print(f"\nCompliance Health Check: {'FOUND' if ch else 'MISSING'}")
    
    if ch:
        print(f"  Severity: {ch.get('severity')}")
        print(f"  Coverage: {ch.get('evidence', {}).get('coverage_percent')}%")
        print(f"  Unknown: {ch.get('evidence', {}).get('unknown')}")
        print(f"  Required: {ch.get('evidence', {}).get('required_total')}")
        print(f"\n[OK] PATCH 13A-0 VERIFIED IN PRODUCTION")
    else:
        print(f"\n[FAIL] Deployment not complete yet (SHA: {sha[:8]})")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
