"""EXHAUSTIVE PLATFORM HEALTH CHECK - Find EVERY broken thing."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("EXHAUSTIVE PLATFORM HEALTH CHECK")
print("=" * 80)

# Check ALL operator endpoints on control.html
operator_endpoints = [
    # Intelligence panels
    ("/api/operator/acquisition-intelligence", "Acquisition Intelligence"),
    ("/api/operator/reddit-acquisition", "Reddit Acquisition"),
    ("/api/operator/compliance-intelligence", "Compliance Intelligence"),
    ("/api/operator/evidence-intelligence?project_id=test", "Evidence Intelligence (needs param)"),
    ("/api/operator/customer-friction", "Customer Friction"),
    ("/api/operator/organism-observability", "Organism Observability"),
    ("/api/operator/operational-alerts", "Operational Alerts"),
    
    # Intake & Queue
    ("/api/operator/intake/queue", "Intake Queue"),
    ("/api/operator/intake/diagnostics", "Intake Diagnostics"),
    ("/api/operator/storage-status", "Storage Status"),
    
    # Organism state
    ("/api/operator/organism/state", "Organism State"),
    ("/api/cognitive-topology", "Cognitive Topology"),
    ("/api/operator/telemetry-status", "Telemetry Status"),
    
    # Knowledge
    ("/api/operator/knowledge-cockpit/search?q=test", "Knowledge Search"),
    
    # SMTP
    ("/api/operator/smtp-status", "SMTP Status"),
    
    # New endpoints I created
    ("/api/operator/acquisition/pending", "Acquisition Pending"),
    ("/api/operator/acquisition/reddit/queue", "Reddit Queue Status"),
    ("/api/operator/vio/status", "VIO Status"),
    ("/api/operator/knowledge/status", "Knowledge Status"),
    ("/api/operator/evidence-intelligence/status", "Evidence Intel Status"),
    ("/api/operator/memory/integrity", "Memory Integrity"),
    ("/api/operator/learning/status", "Learning Status"),
]

print(f"\n[1] Testing {len(operator_endpoints)} operator endpoints...\n")

working = []
broken = []
slow = []

for endpoint, name in operator_endpoints:
    try:
        import time
        start = time.time()
        r = client.get(f"{base_url}{endpoint}", timeout=20)
        elapsed = time.time() - start
        
        if r.status_code == 200:
            data = r.json()
            ok = data.get('ok', True)
            
            if ok:
                status = "[OK]"
                if elapsed > 10:
                    status = "[SLOW]"
                    slow.append((name, endpoint, elapsed))
                print(f"{status:8} {name:40} {elapsed:.2f}s")
                working.append((name, endpoint, elapsed))
            else:
                print(f"[FAIL]   {name:40} ok=false: {data.get('error', 'unknown')}")
                broken.append((name, endpoint, f"ok=false: {data.get('error')}"))
        else:
            print(f"[FAIL]   {name:40} HTTP {r.status_code}")
            broken.append((name, endpoint, f"HTTP {r.status_code}"))
    except Exception as e:
        print(f"[ERROR]  {name:40} {str(e)[:60]}")
        broken.append((name, endpoint, str(e)))

# Check for timeout configuration in other JS files
print("\n" + "=" * 80)
print("[2] Checking for other timeout configurations...\n")

js_files = [
    "ui/assets/js/cockpit-stabilization.js",
    "ui/assets/js/operator-cockpit.js",
    "ui/assets/js/cognitive-topology.js",
    "ui/assets/js/cockpit-intake.js",
]

ROOT = Path("E:/JetFighter_Compliance")
timeout_issues = []

for js_file in js_files:
    path = ROOT / js_file
    if path.is_file():
        content = path.read_text(encoding="utf-8", errors="ignore")
        # Look for timeout configurations
        import re
        timeouts = re.findall(r'(timeout|TIMEOUT)[^=]*=\s*(\d+)', content, re.IGNORECASE)
        for match in timeouts:
            ms = int(match[1])
            if ms < 10000:  # Less than 10 seconds
                timeout_issues.append((js_file, match[0], ms))
                print(f"[WARN] {js_file}: {match[0]} = {ms}ms (< 10s)")

if not timeout_issues:
    print("[OK] No short timeouts found")

# Check circuit breaker status
print("\n" + "=" * 80)
print("[3] Summary\n")

print(f"Working endpoints: {len(working)}/{len(operator_endpoints)}")
print(f"Broken endpoints: {len(broken)}/{len(operator_endpoints)}")
print(f"Slow endpoints (>10s): {len(slow)}")

if broken:
    print("\n[BROKEN ENDPOINTS]")
    for name, endpoint, error in broken:
        print(f"  {name}")
        print(f"    {endpoint}")
        print(f"    {error}")

if slow:
    print("\n[SLOW ENDPOINTS - May timeout in UI]")
    for name, endpoint, elapsed in slow:
        print(f"  {name}: {elapsed:.2f}s")
        if elapsed > 15:
            print(f"    WARNING: Still slower than 15s timeout!")

print("\n" + "=" * 80)
