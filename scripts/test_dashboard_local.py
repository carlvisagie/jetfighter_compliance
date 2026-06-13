"""Test operator dashboard locally."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.acquisition.orchestration import get_operator_dashboard

try:
    result = get_operator_dashboard()
    print("SUCCESS!")
    print(f"Keys: {list(result.keys())}")
    print(f"Hottest targets: {len(result.get('hottest_targets', []))}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
