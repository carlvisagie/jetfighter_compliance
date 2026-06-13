"""Test cognitive topology locally to find the error."""
import sys
from pathlib import Path
import traceback

# Add repo root to path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from services.cognitive_topology import build_cognitive_topology
    
    print("Building cognitive topology...")
    result = build_cognitive_topology()
    
    print("\nSUCCESS!")
    print(f"OK: {result.get('ok')}")
    print(f"System Health: {result.get('system_health')}")
    print(f"Subsystems: {list(result.get('subsystems', {}).keys())}")
    
except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    
    # Try to identify the specific failing component
    print("\n" + "=" * 80)
    print("Attempting to isolate the failure...")
    print("=" * 80)
    
    # Test individual components
    try:
        from services.cognitive_topology import readiness_checks
        print("\n[OK] readiness_checks() works")
        checks = readiness_checks()
        print(f"  Returned {len(checks)} checks")
    except Exception as e2:
        print(f"\n[FAIL] readiness_checks() FAILED: {e2}")
    
    try:
        from services.cognitive_topology import _tail_telemetry
        print("\n[OK] _tail_telemetry() works")
        rows = _tail_telemetry(10)
        print(f"  Returned {len(rows)} rows")
    except Exception as e2:
        print(f"\n[FAIL] _tail_telemetry() FAILED: {e2}")
    
    try:
        from services.cognitive_topology import _project_upload_signal
        print("\n[OK] _project_upload_signal() works")
        result = _project_upload_signal()
        print(f"  Returned: {result}")
    except Exception as e2:
        print(f"\n[FAIL] _project_upload_signal() FAILED: {e2}")
