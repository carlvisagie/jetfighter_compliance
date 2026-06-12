import os, json, glob

projects = [
    'data/projects/FB-VIODEMO001',
    'data/projects/P-VIODEMO002',
    'data/projects/P-VIODEMO003',
    'data/projects/P-VIODEMO004',
    'data/projects/P-VIODEMO005'
]

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
    intake = load_json(f'{p}/communications/intake.json') or {}
    
    # Check if there is an intake file in the data/intakes/ directory just in case
    intake_id = os.path.basename(p).replace('P-', 'FB-')
    if not intake:
        intake = load_json(f'data/intakes/{intake_id}/intake.json') or {}
        
    profile = load_json(f'{p}/evidence/profile.json') or {}
    gaps_data = load_json(f'{p}/evidence/gaps.json') or {}
    gaps = gaps_data.get('gaps', []) if isinstance(gaps_data, dict) else gaps_data
    classifications = load_jsonl(f'{p}/evidence/classifications.jsonl')
    entities = load_jsonl(f'{p}/evidence/entities.jsonl')
    review_queue = load_jsonl(f'{p}/evidence/review_queue.jsonl')
    timelines = load_jsonl(f'{p}/evidence/timelines.jsonl')
    
    cog_summary = load_json(f'{p}/cognition/cognition_summary.json')
    next_actions = load_json(f'{p}/cognition/next_actions.json')
    
    ev_dir = f'{p}/evidence'
    files = [f for f in os.listdir(ev_dir) if os.path.isfile(os.path.join(ev_dir, f)) and not f.endswith('.json') and not f.endswith('.jsonl') and f not in ('00_manifest.txt', '.DS_Store')] if os.path.exists(ev_dir) else []
    
    company_name = profile.get('company_name', intake.get('company', 'Unknown'))
    
    print(f'1. Company name: {company_name}')
    print(f'2. Project/intake ID: {os.path.basename(p)}')
    print(f'3. Files uploaded: {files}')
    print(f'4. Files classified: {len(classifications)}')
    print(f'5. Entities extracted: {len(entities)}')
    print(f'6. Compliance domain detected: {profile.get("compliance_domain")}')
    print(f'7. Gaps detected: {len(gaps)}')
    print(f'8. Cognition summary created: {"Yes" if cog_summary else "No"}')
    
    gen_docs_dir = f'{p}/evidence/generated_documents'
    gen_docs = [f for f in os.listdir(gen_docs_dir)] if os.path.exists(gen_docs_dir) else []
    print(f'9. Generated documents created: {"Yes" if gen_docs else "No"} ({len(gen_docs)} docs)')
    print(f'10. Next actions created: {"Yes" if next_actions else "No"}')
    print(f'11. Customer draft created: {"Yes" if gen_docs else "No"}')
    print(f'12. Review queue items: {len(review_queue)}')
    print(f'13. Memory/timeline events: {len(timelines)}')
    
    cl = load_json(f'{p}/checklist.json') or []
    dash_state = 'Unknown'
    if cl: dash_state = f'{len([t for t in cl if t.get("status")=="done"])}/{len(cl)} done'
    print(f'14. Dashboard state: {dash_state}')
    
    if cog_summary:
        state = cog_summary.get('state', {})
        knows = state.get('knows', [])
        dk = state.get('does_not_know', [])
        print(f'15. What the organism understood: {knows}')
        
        resolutions = cog_summary.get('gap_resolutions', [])
        created = [r for r in resolutions if r.get('strategy') == 'CREATE']
        print(f'16. What the organism created: {created}')
        
        print(f'17. What the organism still needs: {dk}')
        
        asked_unnec = [r for r in resolutions if r.get('strategy') == 'REQUEST' and r.get('confidence_level', 0) >= 0.7]
        print(f'18. What it asked unnecessarily: {asked_unnec}')
        
        should_have_inf = [r for r in resolutions if r.get('strategy') == 'REQUEST' and r.get('confidence_level', 0) >= 0.7]
        print(f'19. What it should have inferred but did not: {should_have_inf}')
    else:
        print('15. What the organism understood: None (Cognition did not run)')
        print('16. What the organism created: None (Cognition did not run)')
        print('17. What the organism still needs: ' + str([g.get('gap_type', g.get('gap_id')) for g in gaps]))
        print('18. What it asked unnecessarily: Unknown (Cognition did not run)')
        print('19. What it should have inferred but did not: Unknown (Cognition did not run)')
        
    print('--- DETAILS ---')
    print(f'Profile details: {profile}')
    print('Gaps:')
    for g in gaps:
        print(f' - {g.get("gap_type", g.get("gap_id", "Unknown"))}: {g.get("description")}')
    print('Entities:')
    for e in entities:
        print(f' - {e.get("field")}: {e.get("value")} (conf: {e.get("confidence")})')
