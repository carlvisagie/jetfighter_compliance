"""COMPREHENSIVE PRODUCTION SYSTEM CHECK - ALL SUBSYSTEMS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("COMPREHENSIVE PRODUCTION SYSTEM CHECK")
print("=" * 80)

# List of all critical endpoints to check
endpoints = [
    # Acquisition Intelligence
    ("/api/operator/acquisition/pending", "GET", "Acquisition Intelligence - Pending"),
    ("/api/operator/acquisition/reddit/queue", "GET", "Reddit Acquisition Queue"),
    
    # Cognitive Topology (already fixed)
    ("/api/cognitive-topology", "GET", "Cognitive Topology"),
    
    # Intake Queue (already checked)
    ("/api/operator/intake/queue", "GET", "Intake Queue"),
    
    # Organism State (already checked)
    ("/api/operator/organism/state", "GET", "Organism State"),
    
    # VIO Intelligence
    ("/api/operator/vio/status", "GET", "VIO Status"),
    
    # Knowledge Base
    ("/api/operator/knowledge/status", "GET", "Knowledge Status"),
    
    # Evidence Intelligence
    ("/api/operator/evidence-intelligence/status", "GET", "Evidence Intelligence"),
    
    # Memory Systems
    ("/api/operator/memory/integrity", "GET", "Memory Integrity"),
    
    # Learning System
    ("/api/operator/learning/status", "GET", "Learning Status"),
    
    # Observability
    ("/api/operator/organism-observability", "GET", "Organism Observability"),
]

print("\nChecking all critical endpoints...\n")

failed_endpoints = []
working_endpoints = []

for endpoint, method, name in endpoints:
    try:
        if method == "GET":
            r = client.get(f"{base_url}{endpoint}")
        else:
            continue
        
        status = r.status_code
        
        if status == 200:
            data = r.json()
            ok = data.get('ok', True)
            
            if ok:
                print(f"[OK] {name}")
                print(f"     {endpoint} -> {status}")
                working_endpoints.append((name, endpoint, status))
            else:
                error = data.get('error', 'Unknown error')
                print(f"[FAIL] {name}")
                print(f"       {endpoint} -> {status} (ok=false)")
                print(f"       Error: {error}")
                failed_endpoints.append((name, endpoint, status, error))
        elif status == 404:
            print(f"[NOT FOUND] {name}")
            print(f"            {endpoint} -> 404")
            failed_endpoints.append((name, endpoint, 404, "Endpoint does not exist"))
        elif status == 500:
            print(f"[SERVER ERROR] {name}")
            print(f"               {endpoint} -> 500")
            body = r.text[:200] if r.text else "No response body"
            failed_endpoints.append((name, endpoint, 500, body))
        else:
            print(f"[ERROR] {name}")
            print(f"        {endpoint} -> {status}")
            failed_endpoints.append((name, endpoint, status, "Unexpected status"))
            
    except Exception as e:
        print(f"[EXCEPTION] {name}")
        print(f"            {endpoint}")
        print(f"            Error: {e}")
        failed_endpoints.append((name, endpoint, 0, str(e)))

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\nWorking endpoints: {len(working_endpoints)}")
print(f"Failed endpoints: {len(failed_endpoints)}")

if failed_endpoints:
    print("\n" + "=" * 80)
    print("FAILED ENDPOINTS - REQUIRE IMMEDIATE ATTENTION")
    print("=" * 80)
    
    for name, endpoint, status, error in failed_endpoints:
        print(f"\n{name}")
        print(f"  Endpoint: {endpoint}")
        print(f"  Status: {status}")
        print(f"  Error: {error}")
        
print("\n" + "=" * 80)
