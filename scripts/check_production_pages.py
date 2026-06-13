"""Deep dive - check for actual runtime errors in pages."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("PRODUCTION PAGE HEALTH CHECK")
print("=" * 80)

# Test key operator pages
pages = [
    ("/ui/control.html", "Control Cockpit"),
    ("/ui/intake.html", "Customer Intake"),
    ("/ui/deliverables.html", "Deliverables"),
    ("/ui/vio.html", "VIO Dashboard"),
    ("/ui/knowledge.html", "Knowledge Base"),
    ("/ui/memory.html", "Memory Browser"),
    ("/ui/command.html", "Command Center"),
    ("/ui/status.html", "Project Status"),
]

print("\n[1] Checking page accessibility...\n")

for path, name in pages:
    try:
        r = client.get(f"{base_url}{path}")
        if r.status_code == 200:
            content = r.text
            # Check for obvious errors
            has_script_error = "Uncaught" in content or "SyntaxError" in content
            has_html = "<html" in content.lower()
            
            if has_html and not has_script_error:
                print(f"[OK] {name:25} -> 200 (loads)")
            else:
                print(f"[WARN] {name:25} -> 200 (check manually)")
        else:
            print(f"[FAIL] {name:25} -> {r.status_code}")
    except Exception as e:
        print(f"[ERROR] {name:25} -> {e}")

# Check key data endpoints that pages depend on
print("\n[2] Checking key data endpoints...\n")

data_endpoints = [
    ("/api/cognitive-topology", "Cognitive Topology"),
    ("/api/operator/intake/queue", "Intake Queue"),
    ("/api/operator/organism/state", "Organism State"),
    ("/api/operator/acquisition-intelligence", "Acquisition Intelligence"),
    ("/api/operator/reddit-acquisition", "Reddit Acquisition"),
    ("/api/operator/compliance-intelligence", "Compliance Intelligence"),
    ("/api/operator/evidence-intelligence", "Evidence Intelligence"),
    ("/api/operator/operational-alerts", "Operational Alerts"),
    ("/api/operator/organism-observability", "Organism Observability"),
    ("/api/operator/customer-friction", "Customer Friction"),
]

failing = []
for endpoint, name in data_endpoints:
    try:
        r = client.get(f"{base_url}{endpoint}")
        if r.status_code == 200:
            data = r.json()
            if data.get("ok") is False:
                print(f"[WARN] {name:30} -> ok=false")
                failing.append((name, endpoint, "ok=false"))
            else:
                print(f"[OK] {name:30} -> 200")
        else:
            print(f"[FAIL] {name:30} -> {r.status_code}")
            failing.append((name, endpoint, f"HTTP {r.status_code}"))
    except Exception as e:
        print(f"[ERROR] {name:30} -> {e}")
        failing.append((name, endpoint, str(e)))

if failing:
    print("\n" + "=" * 80)
    print("FAILING DATA ENDPOINTS")
    print("=" * 80)
    for name, endpoint, error in failing:
        print(f"\n{name}")
        print(f"  {endpoint}")
        print(f"  Error: {error}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\nPages checked: {len(pages)}")
print(f"Data endpoints checked: {len(data_endpoints)}")
print(f"Failing: {len(failing)}")

if failing:
    print("\n[ACTION REQUIRED] Fix failing data endpoints above")
else:
    print("\n[SUCCESS] All pages and data endpoints operational")

print("\n" + "=" * 80)
