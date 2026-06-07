import json
import os
import shutil
from pathlib import Path

# Enable OCR
os.environ["KYC_OCR_ENABLED"] = "true"

from services.durable_storage import active_data_root
from services.evidence_intelligence import process_evidence_upload
from services.evidence_intelligence.storage import wipe_rebuildable_artifacts, load_review_queue, load_jsonl
from services.cognition.storage import run_cognition_safely, get_cognition_state

def run_company_20():
    project_id = "company_20"
    base_dir = Path(r"E:\JetFighter_Compliance\data\adversarial_corpus\adversarial_test_corpus\company_20\uploads")
    
    upload_files = []
    if base_dir.exists():
        for f in base_dir.iterdir():
            if f.is_file():
                upload_files.append(f)
                
    project_evidence = active_data_root() / "projects" / project_id / "evidence" / "uploads"
    project_evidence.mkdir(parents=True, exist_ok=True)
    
    wipe_rebuildable_artifacts(project_id)
    
    print(f"Running EI with OCR for {len(upload_files)} files...")
    for f in upload_files:
        dest_file = project_evidence / f.name
        shutil.copy2(f, dest_file)
        
        process_evidence_upload(project_id=project_id, file_path=dest_file)
        
    print("Running cognition...")
    run_cognition_safely(project_id)
    
    extractions = load_jsonl(project_id, "extractions.jsonl")
    print("\n--- OCR Results ---")
    for ex in extractions:
        if ex.get("ocr_status"):
            print(f"{ex['source_file']}: OCR status = {ex['ocr_status']} | Warnings = {ex.get('warnings')}")

    rq = load_review_queue(project_id)
    print("\n--- Review Queue Items ---")
    for r in rq:
        print(f"[{r.get('kind')}] {r.get('file')} - {r.get('reason', '')}")
        
    state_resp = get_cognition_state(project_id)
    validation = state_resp.get("validation_report", {})
    
    print("\n--- Cognition Validation ---")
    print("Documents generated:")
    for d in validation.get("documents_generated", []):
        print(f"  - {d.get('document_type')} (Confidence: {d.get('confidence_score')})")
        
    print("Human review flags:")
    for hr in validation.get("human_review_items", []):
        print(f"  - [{hr.get('item_type')}] {hr.get('reason')}")

if __name__ == "__main__":
    run_company_20()
