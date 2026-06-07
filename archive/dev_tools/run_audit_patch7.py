import os
import json
import logging
from services.cognition.storage import run_cognition_safely

logging.basicConfig(level=logging.INFO)

projects = [
    'FB-VIODEMO001',
    'P-VIODEMO002',
    'P-VIODEMO003',
    'P-VIODEMO004',
    'P-VIODEMO005'
]

def load_json(path):
    if os.path.exists(path):
        try: return json.load(open(path))
        except: return None
    return None

results = []

for p in projects:
    intake_id = p.replace('P-', 'FB-')
    
    # Read Before State
    cog_summary_before = load_json(f'data/projects/{intake_id}/cognition/cognition_summary.json') or {}
    gaps_before = cog_summary_before.get("gap_resolutions", [])
    total_gaps_before = len(gaps_before)
    requests_before = [r for r in gaps_before if r.get("strategy", "").upper() == "REQUEST"]
    gen_docs_before = [r for r in gaps_before if r.get("strategy", "").upper() != "REQUEST"]
    
    if total_gaps_before > 0:
        elim_before = ((total_gaps_before - len(requests_before)) / total_gaps_before) * 100
    else:
        elim_before = 0.0

    # Re-run Cognition (Patch 7 engine)
    run_cognition_safely(intake_id)

    # Read After State
    cog_summary_after = load_json(f'data/projects/{intake_id}/cognition/cognition_summary.json') or {}
    gaps_after = cog_summary_after.get("gap_resolutions", [])
    total_gaps_after = len(gaps_after)
    requests_after = [r for r in gaps_after if r.get("strategy", "").upper() == "REQUEST"]
    gen_docs_after = [r for r in gaps_after if r.get("strategy", "").upper() != "REQUEST"]
    
    if total_gaps_after > 0:
        elim_after = ((total_gaps_after - len(requests_after)) / total_gaps_after) * 100
    else:
        elim_after = 0.0
        
    explanations = load_json(f'data/projects/{intake_id}/cognition/generation_explanation.json') or []

    results.append({
        "company": intake_id,
        "total_gaps_before": total_gaps_before,
        "elim_before": elim_before,
        "elim_after": elim_after,
        "gen_docs_before": [r.get("target_document_type") for r in gen_docs_before],
        "gen_docs_after": [r.get("target_document_type") for r in gen_docs_after],
        "reqs_before": [r.get("gap_id") for r in requests_before],
        "reqs_after": [r.get("gap_id") for r in requests_after],
        "explanations": explanations
    })

print("\n" + "="*80)
print("PATCH 7 ORGANISM AUDIT RESULTS")
print("="*80)

total_elim_before = 0
total_elim_after = 0
all_gen_docs = []
all_reqs = []

for r in results:
    print(f"\n--- Company: {r['company']} ---")
    print(f"1. Previous workload elimination %: {r['elim_before']:.1f}%")
    print(f"2. New workload elimination %:      {r['elim_after']:.1f}%")
    print(f"3. Documents generated before:      {r['gen_docs_before']}")
    print(f"4. Documents generated after:       {r['gen_docs_after']}")
    print(f"5. Questions asked before:          {r['reqs_before']}")
    print(f"6. Questions asked after:           {r['reqs_after']}")
    
    total_elim_before += r['elim_before']
    total_elim_after += r['elim_after']
    all_gen_docs.extend(r['gen_docs_after'])
    all_reqs.extend(r['reqs_after'])

avg_before = total_elim_before / len(results)
avg_after = total_elim_after / len(results)
net_improvement = avg_after - avg_before

from collections import Counter
top_docs = [item[0] for item in Counter(all_gen_docs).most_common(5)]
top_reqs = [item[0] for item in Counter(all_reqs).most_common(5)]

print("\n" + "="*80)
print("SUMMARY METRICS")
print("="*80)
print(f"A. Average workload elimination before Patch 7: {avg_before:.1f}%")
print(f"B. Average workload elimination after Patch 7:  {avg_after:.1f}%")
print(f"C. Net improvement:                             +{net_improvement:.1f}%")
print(f"D. Top generated document types:                {top_docs}")
print(f"E. Remaining irreducible customer requests:     {top_reqs}")

