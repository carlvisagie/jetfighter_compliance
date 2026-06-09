import sys
import json
import httpx
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(_REPO))

from scripts.lib.ops_client import authenticate_production

def main():
    print("Verifying PATCH 12J in production...")
    public_url = "https://compliance.keepyourcontracts.com/api/intake/upload"
    
    # Wait for deployment
    max_retries = 30
    for i in range(max_retries):
        files_unsupported = [
            ("files", ("test.exe", b"MZ90", "application/x-msdownload"))
        ]
        data_unsupported = {
            "email": "carl+aegis_test@keepyourcontracts.com",
            "company": "Aegis",
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["test.exe"])
        }
        
        try:
            r = httpx.post(public_url, files=files_unsupported, data=data_unsupported)
            if r.status_code == 400:
                detail = r.json().get("detail", "")
                if "Allowed formats: PDF" in detail:
                    print(f"Deployment verified live after {i*10} seconds!")
                    break
        except Exception:
            pass
            
        print(f"Waiting for deploy... ({i}/{max_retries})")
        time.sleep(10)
    else:
        print("Timeout waiting for deploy.")
        return

    # 1. Test unsupported file rejection
    print("\n--- Testing unsupported file (.exe) ---")
    files_unsupported = [
        ("files", ("test.exe", b"MZ90", "application/x-msdownload"))
    ]
    data_unsupported = {
        "email": "carl+aegis_test@keepyourcontracts.com",
        "company": "Aegis",
        "expected_file_count": "1",
        "expected_file_names": json.dumps(["test.exe"])
    }
    
    r_unsupp = httpx.post(public_url, files=files_unsupported, data=data_unsupported)
    if r_unsupp.status_code != 400:
        print(f"FAILED: Expected 400 (graceful rejection), got {r_unsupp.status_code}")
    else:
        reason = r_unsupp.json().get("detail", "")
        print(f"Rejected reason: {reason}")
        if "Allowed formats: PDF, Word, Excel, ZIP, images, CSV, TXT, JSON, XML, MD, YAML, LOG, HTML, EML, MSG." in reason:
            print("PASS: Unsupported message is correct.")
        else:
            print("FAIL: Unsupported message is incorrect.")

    # 2. Test JSON upload and classification
    print("\n--- Testing JSON upload and classification ---")
    files_json = [
        ("files", ("company_profile.json", b'{"test": 1}', "application/json")),
        ("files", ("ground_truth.json", b'{"test": 2}', "application/json"))
    ]
    data_json = {
        "email": "carl+aegis_test@keepyourcontracts.com",
        "company": "Aegis",
        "expected_file_count": "2",
        "expected_file_names": json.dumps(["company_profile.json", "ground_truth.json"])
    }
    
    r_json = httpx.post(public_url, files=files_json, data=data_json)
    if r_json.status_code != 200:
        print(f"FAILED: Expected 200, got {r_json.status_code}")
        print(r_json.text)
        return
        
    res = r_json.json()
    intake_id = res.get("intake_id")
    print(f"Upload successful. Intake ID: {intake_id}")
    print(f"Expected file count: {res.get('expected_file_count')}")
    print(f"Verified file count: {res.get('verified_file_count')}")
    print(f"Rejected file count: {res.get('rejected_file_count')}")
    
    if res.get("verified_file_count") != 2:
        print("FAIL: Not all files were verified.")
    else:
        print("PASS: JSON files received and verified.")

    # 3. Check Classification using operator API
    print("\n--- Checking classification ---")
    client, _, _ = authenticate_production()
    
    # Give the background classification a second to run (if it's async)
    time.sleep(2)
    
    # The durable layer is synced with the API. We can just read the local filesystem because our production uses active_data_root! 
    # Wait, the production server might be remote, but the current `E:\JetFighter_Compliance` acts as the master.
    # Ah, the API runs remotely. We cannot read the remote disk using `open()` here. We need to query the API.
    r_intake = client.get(f"https://compliance.keepyourcontracts.com/api/operator/intake/{intake_id}/files")
    if r_intake.status_code == 200:
        pass
        
    r_dash = client.get("https://compliance.keepyourcontracts.com/api/operator/intake/dashboard")
    
    # To get the classification, we can hit the /api/operator/intake/{intake_id}
    r_details = client.get(f"https://compliance.keepyourcontracts.com/api/operator/intake/{intake_id}")
    
    if r_details.status_code == 200:
        # Actually, classification results are returned as part of the intake record, but we might not have it in the top level.
        # Let's hit the cognition endpoint? The cognition doesn't run for founding pilots until operator kicks it off, 
        # but `classify_intake` does run and save to classification.json. Does the operator API return it?
        pass

    # Let's try to find how to read classification remotely, or let's use the local storage since the remote might be syncing
    # or the remote actually IS this environment via some tunnels. 
    # Let's try reading the local file. If it doesn't exist, we're testing the remote server and we can't see the file.
    from services.intake.storage import intake_dir
    classification_path = intake_dir(intake_id) / "classification.json"
    
    # Wait, the prompt says "VERIFY PATCH 12J IN PRODUCTION. Check production build contains commit: 7392c23"
    # But then "run a clean Aegis upload through the customer portal".
    # And "organism remains stable".
    # Let me just print the local path, it might be that this IS the production environment.
    if classification_path.exists():
        clf_data = json.loads(classification_path.read_text(encoding="utf-8"))
        print("\nClassification results:")
        for f in clf_data.get("files", []):
            print(f"- {f.get('filename')}: {f.get('category')}")
            
        cp_cat = next((f.get("category") for f in clf_data.get("files", []) if f.get("filename") == "company_profile.json"), None)
        gt_cat = next((f.get("category") for f in clf_data.get("files", []) if f.get("filename") == "ground_truth.json"), None)
        
        if cp_cat == "Structured metadata":
            print("PASS: company_profile.json classified as Structured metadata")
        else:
            print(f"FAIL: company_profile.json classified as {cp_cat}")
            
        if gt_cat == "Test artifact":
            print("PASS: ground_truth.json classified as Test artifact")
        else:
            print(f"FAIL: ground_truth.json classified as {gt_cat}")
            
    else:
        print("FAIL: classification.json not found for intake locally.")
        print("This means the upload happened remotely and we cannot verify the classification via local disk.")
        print("Checking remote /api/operator/intake/{id}...")
        print(r_details.json())

if __name__ == "__main__":
    main()