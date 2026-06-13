"""Check production runtime configuration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("PRODUCTION RUNTIME CONFIGURATION")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/ops/boot-status")
    r.raise_for_status()
    boot = r.json()
    
    print(f"\nSafe Mode: {boot.get('safe_mode')}")
    print(f"Schedulers Enabled: {boot.get('schedulers_enabled')}")
    print(f"Knowledge Overlay: {boot.get('knowledge_overlay_enabled')}")
    print(f"Manual Acquisition: {boot.get('manual_acquisition_enabled')}")
    print(f"Observability: {boot.get('observability_enabled')}")
    
    env_vars = boot.get('env', {})
    print(f"\nEnvironment Variables:")
    for key in ['KYC_SAFE_MODE', 'KYC_SCHEDULERS_ENABLED', 'KYC_KNOWLEDGE_OVERLAY_ENABLED']:
        value = env_vars.get(key, 'NOT SET')
        print(f"  {key}: {value}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
