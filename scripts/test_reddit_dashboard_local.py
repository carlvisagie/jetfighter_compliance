"""Test reddit operator dashboard locally."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from services.acquisition.connectors.reddit import get_operator_dashboard
    
    print("Import successful!")
    print(f"Function: {get_operator_dashboard}")
    
    print("\nCalling get_operator_dashboard()...")
    result = get_operator_dashboard()
    
    print(f"\nSuccess! Got result:")
    print(f"  ok: {result.get('ok')}")
    print(f"  connector: {result.get('connector')}")
    print(f"  pending_opportunities: {len(result.get('pending_opportunities', []))}")
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
