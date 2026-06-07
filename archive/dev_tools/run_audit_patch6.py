import os
import json
import logging
from services.evidence_intelligence.freshness import sweep_intakes_for_staleness

logging.basicConfig(level=logging.INFO)

projects = [
    'FB-VIODEMO001',
    'P-VIODEMO002',
    'P-VIODEMO003',
    'P-VIODEMO004',
    'P-VIODEMO005'
]

# Run sweep first on the actual intake ids
intake_ids = [p.replace('P-', 'FB-') for p in projects]
print("Running sweep...")
sweep_res = sweep_intakes_for_staleness(intake_ids=intake_ids, max_reprocess=10)
print(f"Sweep results: scanned={sweep_res.get('scanned')}, stale={len(sweep_res.get('stale', []))}, reprocessed={len(sweep_res.get('reprocessed', []))}, failed={len(sweep_res.get('failed', []))}")
if sweep_res.get('failed'):
    print("Sweep failures:", json.dumps(sweep_res['failed'], indent=2))

def load_json(path):
    if os.path.exists(path):
        try: return json.load(open(path))
        except: return None
    return None

def load_jsonl(path):
    res = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    try: res.append(json.loads(line))
                    except: pass
    return res

for p in projects:
    print('='*80)
    print(f'PROJECT: {p}')
    intake = load_json(f'data/projects/{p}/communications/intake.json') or {}
    
    intake_id = p.replace('P-', 'FB-')
    if not intake:
        intake = load_json(f'data/intakes/{intake_id}/intake.json') or {}
        
    intel_dir = f'data/projects/{intake_id}/evidence_intelligence'
    
    profile = load_json(f'{intel_dir}/profile.json') or load_json(f'data/projects/{intake_id}/evidence/profile.json') or {}
    gaps_data = load_json(f'{intel_dir}/gaps.json') or load_json(f'data/projects/{intake_id}/evidence/gaps.json') or {}
    gaps = gaps_data.get('gaps', []) if isinstance(gaps_data, dict) else gaps_data
    classifications = load_jsonl(f'{intel_dir}/classifications.jsonl') or load_jsonl(f'data/projects/{intake_id}/evidence/classifications.jsonl')
    entities = load_jsonl(f'{intel_dir}/entities.jsonl') or load_jsonl(f'data/projects/{intake_id}/evidence/entities.jsonl')
    review_queue = load_jsonl(f'{intel_dir}/review_queue.jsonl') or load_jsonl(f'data/projects/{intake_id}/evidence/review_queue.jsonl')
    timelines = load_jsonl(f'data/projects/{intake_id}/evidence/timelines.jsonl')
    
    cog_summary = load_json(f'data/projects/{intake_id}/cognition/cognition_summary.json') or {}
    
    ev_dir = f'data/projects/{intake_id}/evidence'
    
    if not os.path.exists(ev_dir) and os.path.exists(f'data/intakes/{intake_id}/uploads'):
        files = os.listdir(f'data/intakes/{intake_id}/uploads')
    else:
        files = [f for f in os.listdir(ev_dir) if os.path.isfile(os.path.join(ev_dir, f)) and not f.endswith('.json') and not f.endswith('.jsonl') and f not in ('00_manifest.txt', '.DS_Store')] if os.path.exists(ev_dir) else []
        
    company_name = profile.get('company_name', intake.get('company', 'Unknown'))
    
    # Check extractions for success
    extractions = load_jsonl(f'{intel_dir}/extractions.jsonl') if os.path.exists(intel_dir) else []
    success_files = [e.get('artifact_id') for e in extractions if e.get('status') == 'completed']
    
    print(f'1. Company Name: {company_name}')
    print(f'2. Files Uploaded: {files}')
    print(f'3. Files Successfully Processed: {success_files}')
    print(f'4. Classification Results: {[c.get("document_type") for c in classifications]}')
    print(f'5. Extracted Entities: {[e.get("type") + ":" + str(e.get("value")) for e in entities]}')
    print(f'6. Detected Compliance Domain: {profile.get("primary_domain")}')
    print(f'7. Gaps Identified: {[g.get("gap_id") for g in gaps]}')
    print(f'8. Cognition Summary Generated?: {"Yes" if cog_summary else "No"}')
    
    gen_docs = cog_summary.get("generated_documents", [])
    print(f'9. Documents Auto-Generated: {[d.get("doc_type") for d in gen_docs]}')
    
    requests = [r for r in cog_summary.get("gap_resolutions", []) if r.get("strategy").upper() == "REQUEST"]
    print(f'10. Customer Questions Generated: {[r.get("gap_id") for r in requests]}')
    
    print(f'11. Remaining Missing Information: {cog_summary.get("state", {}).get("does_not_know", [])}')
    
    # errors
    errors = [e.get('error') for e in extractions if e.get('status') == 'failed']
    # blind events?
    blind_events = [q.get('reason') for q in review_queue if q.get('kind') == 'evidence_intelligence_blind']
    all_errors = errors + blind_events
    print(f'12. Current Stage: {"Cognition complete" if cog_summary else "Failed"}')
    print(f'13. Any Errors Encountered: {all_errors}')
    print('')
