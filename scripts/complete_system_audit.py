"""COMPLETE SYSTEMATIC AUDIT - Find ALL disconnections and broken wiring."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("COMPLETE SYSTEMATIC PLATFORM AUDIT")
print("=" * 80)

issues = []

# 1. Check ALL operator panels have correct data connections
print("\n[1] CHECKING ALL OPERATOR PANELS FOR DATA CONNECTION ISSUES\n")

panel_checks = [
    ("Acquisition Intelligence", "/api/operator/acquisition-intelligence", [
        "hottest_targets",
        "founding_pilot",
        "doctrine",
    ]),
    ("Reddit Acquisition", "/api/operator/reddit-acquisition", [
        "pending_opportunities",
        "queue_diagnostics",
    ]),
    ("Compliance Intelligence", "/api/operator/compliance-intelligence", [
        "pending_changes",
        "monitor_changes",
    ]),
    ("Evidence Intelligence", "/api/operator/evidence-intelligence/status", [
        "health",
        "project_count",
    ]),
    ("Customer Friction", "/api/operator/customer-friction", [
        "continuation_opened",
        "upload_completed",
    ]),
    ("Organism Observability", "/api/operator/organism-observability", [
        "recent_events",
    ]),
    ("Operational Alerts", "/api/operator/operational-alerts", [
        "alerts",
    ]),
]

for name, endpoint, required_fields in panel_checks:
    try:
        r = client.get(f"{base_url}{endpoint}", timeout=20)
        if r.status_code == 200:
            data = r.json()
            if not data.get('ok', True):
                issues.append(f"{name}: API returned ok=false")
                print(f"[ISSUE] {name}: {data.get('error', 'unknown error')}")
                continue
            
            missing = []
            for field in required_fields:
                if field not in data:
                    missing.append(field)
            
            if missing:
                issues.append(f"{name}: Missing fields {missing}")
                print(f"[ISSUE] {name}: Missing fields {missing}")
            else:
                print(f"[OK] {name}")
        else:
            issues.append(f"{name}: HTTP {r.status_code}")
            print(f"[ISSUE] {name}: HTTP {r.status_code}")
    except Exception as e:
        issues.append(f"{name}: {str(e)[:50]}")
        print(f"[ERROR] {name}: {str(e)[:50]}")

# 2. Check for old field names in UI code
print("\n[2] CHECKING UI FOR OLD/WRONG FIELD NAMES\n")

ROOT = Path("E:/JetFighter_Compliance")
UI_HTML = ROOT / "ui" / "control.html"

if UI_HTML.is_file():
    content = UI_HTML.read_text(encoding="utf-8", errors="ignore")
    
    old_patterns = [
        ("fit_score", "OLD scoring - should use prey_score"),
        ("qualification_score", "OLD scoring - should use prey_score"),
        ("overall_confidence", "OLD scoring - should use prey_score"),
    ]
    
    for pattern, issue in old_patterns:
        if pattern in content:
            count = content.count(pattern)
            issues.append(f"UI contains '{pattern}' ({count} times)")
            print(f"[ISSUE] UI still uses '{pattern}' {count} times - {issue}")

# 3. Check for hardcoded timeouts
print("\n[3] CHECKING FOR SHORT TIMEOUTS IN JS\n")

js_files = [
    "ui/assets/js/cockpit-stabilization.js",
    "ui/assets/js/cognitive-topology.js",
]

for js_file in js_files:
    path = ROOT / js_file
    if path.is_file():
        content = path.read_text(encoding="utf-8", errors="ignore")
        import re
        timeouts = re.findall(r'setTimeout\([^,]+,\s*(\d+)\)', content)
        for ms in timeouts:
            if int(ms) < 5000 and int(ms) > 100:  # Between 100ms and 5s
                issues.append(f"{js_file}: Short timeout {ms}ms")
                print(f"[ISSUE] {js_file}: setTimeout {ms}ms (may be too short)")

# 4. Check backend is using tuned engine
print("\n[4] CHECKING BACKEND USES TUNED ACQUISITION ENGINE\n")

orch_file = ROOT / "services" / "acquisition" / "orchestration.py"
if orch_file.is_file():
    content = orch_file.read_text(encoding="utf-8", errors="ignore")
    
    # Check it returns prey_score
    if "prey_score" not in content:
        issues.append("orchestration.py missing prey_score")
        print("[ISSUE] orchestration.py doesn't return prey_score")
    else:
        print("[OK] orchestration.py returns prey_score")
    
    # Check it doesn't return old fields
    if '"fit_score"' in content or '"qualification_score"' in content:
        issues.append("orchestration.py still returns OLD scoring fields")
        print("[ISSUE] orchestration.py still returns fit_score or qualification_score")

# 5. Check for broken imports
print("\n[5] CHECKING FOR MISPLACED IMPORTS\n")

py_files = list((ROOT / "services").rglob("*.py"))
import_issues = []

for f in py_files[:100]:  # Check first 100 Python files
    try:
        content = f.read_text(encoding="utf-8", errors="ignore")
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            if 'from services.defensive_wiring import' in line:
                # Check if inside parentheses
                paren_count = 0
                for j in range(max(0, i-10), i):
                    paren_count += lines[j].count('(') - lines[j].count(')')
                
                if paren_count > 0:
                    rel_path = str(f.relative_to(ROOT))
                    import_issues.append((rel_path, i))
                    issues.append(f"{rel_path}:{i} - misplaced import")
    except Exception:
        pass

if import_issues:
    print(f"[ISSUE] Found {len(import_issues)} files with misplaced imports:")
    for path, line in import_issues[:10]:
        print(f"  {path}:{line}")
else:
    print("[OK] No misplaced imports found")

print("\n" + "=" * 80)
print("AUDIT SUMMARY")
print("=" * 80)

print(f"\nTotal issues found: {len(issues)}")

if issues:
    print("\n[CRITICAL ISSUES]")
    for issue in issues:
        print(f"  - {issue}")
    print("\n[ACTION REQUIRED] Fix all issues listed above")
else:
    print("\n[SUCCESS] No critical issues found")

print("\n" + "=" * 80)
