import sys
import json
import httpx
from pathlib import Path

_REPO = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(_REPO))

from scripts.lib.ops_client import authenticate_production

def main():
    client, _, _ = authenticate_production()
    
    intake_id = "FB-e7540846b591" # The one we just created
    
    # 1. Fetch files from operator API
    r_files = client.get(f"https://compliance.keepyourcontracts.com/api/operator/intake/{intake_id}/files")
    if r_files.status_code == 200:
        data = r_files.json()
        print("FILES ENDPOINT RESPONSE:")
        print(json.dumps(data, indent=2))
        
    # 2. Fetch VIO from operator API
    r_vio = client.get(f"https://compliance.keepyourcontracts.com/api/operator/vio/company/{intake_id}")
    if r_vio.status_code == 200:
        data = r_vio.json()
        print("\nVIO ENDPOINT RESPONSE:")
        print(json.dumps(data, indent=2))
        
    # 3. Fetch cognition from operator API
    # Wait, the cognition endpoint takes project_id. VIO company usually has project_id = intake_id for new intakes.
    r_cog = client.get(f"https://compliance.keepyourcontracts.com/api/operator/cognition/{intake_id}")
    if r_cog.status_code == 200:
        data = r_cog.json()
        print("\nCOGNITION ENDPOINT RESPONSE:")
        print(json.dumps(data, indent=2))
        
if __name__ == "__main__":
    main()
