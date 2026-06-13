"""Check actual qualification scores in production data."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path("E:/JetFighter_Compliance")
DATA_DIR = ROOT / "data"

print("=" * 80)
print("ACQUISITION QUALIFICATION SCORE ANALYSIS")
print("=" * 80)

# Check leads.jsonl
leads_file = DATA_DIR / "acquisition" / "leads.jsonl"

if not leads_file.is_file():
    print("[ERROR] leads.jsonl not found")
    sys.exit(1)

print(f"\n[1] Reading leads from {leads_file}...\n")

leads = []
with open(leads_file, 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            try:
                leads.append(json.loads(line))
            except:
                pass

print(f"Found {len(leads)} leads\n")

if not leads:
    print("[ERROR] No leads found")
    sys.exit(1)

# Analyze qualification scores
qual_scores = []
fit_scores = []
confidence_scores = []

for lead in leads[-20:]:  # Last 20 leads
    company = lead.get('company_name', 'Unknown')
    
    # Check different score fields
    qual = lead.get('qualification', {})
    qual_score = qual.get('overall_confidence', lead.get('confidence_score', 'N/A'))
    fit_score = lead.get('fit_score', 'N/A')
    
    qual_scores.append((company, qual_score))
    fit_scores.append(fit_score)
    
    print(f"{company[:50]:50} | Qual: {qual_score} | Fit: {fit_score}")

# Check if all scores are the same
print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

unique_qual = set(str(q[1]) for q in qual_scores)
unique_fit = set(str(f) for f in fit_scores)

print(f"\nUnique qualification scores: {unique_qual}")
print(f"Unique fit scores: {unique_fit}")

if len(unique_qual) == 1:
    print(f"\n[PROBLEM] ALL leads have the SAME qualification score: {list(unique_qual)[0]}")
    print("This is clearly broken - scores should vary based on company signals")
else:
    print(f"\n[OK] Scores vary across leads")

# Check one lead in detail
if leads:
    print("\n" + "=" * 80)
    print("SAMPLE LEAD DETAIL (most recent)")
    print("=" * 80)
    lead = leads[-1]
    print(f"\nCompany: {lead.get('company_name')}")
    print(f"Source: {lead.get('source')}")
    print(f"Status: {lead.get('status')}")
    print(f"\nScoring fields:")
    print(f"  confidence_score: {lead.get('confidence_score')}")
    print(f"  fit_score: {lead.get('fit_score')}")
    print(f"  acquisition_priority_score: {lead.get('acquisition_priority_score')}")
    
    qual = lead.get('qualification', {})
    if qual:
        print(f"\nQualification object:")
        for key, val in qual.items():
            print(f"  {key}: {val}")
    else:
        print(f"\n[PROBLEM] No qualification object found!")

print("\n" + "=" * 80)
