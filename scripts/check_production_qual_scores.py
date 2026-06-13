"""Query production API for actual qualification scores."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("PRODUCTION ACQUISITION QUALIFICATION SCORE ANALYSIS")
print("=" * 80)

# Get acquisition intelligence
print("\n[1] Fetching acquisition intelligence from production...\n")
r = client.get(f"{base_url}/api/operator/acquisition-intelligence")

if r.status_code != 200:
    print(f"[ERROR] Failed to fetch: {r.status_code}")
    sys.exit(1)

data = r.json()

if not data.get('ok'):
    print(f"[ERROR] API returned ok=false: {data.get('error')}")
    sys.exit(1)

hottest = data.get('hottest_targets', [])

if not hottest:
    print("[INFO] No hottest targets found")
    sys.exit(0)

print(f"Found {len(hottest)} hottest targets\n")
print("=" * 80)
print("QUALIFICATION SCORES")
print("=" * 80)

qual_scores = []
fit_scores = []

for target in hottest:
    company = target.get('company_name', 'Unknown')
    qual_score = target.get('qualification_score', 'N/A')
    fit_score = target.get('fit_score', 'N/A')
    source = target.get('source', 'Unknown')
    status = target.get('status', 'Unknown')
    
    qual_scores.append(qual_score)
    fit_scores.append(fit_score)
    
    print(f"{company[:40]:40} | Qual: {qual_score:>6} | Fit: {fit_score:>6} | {source[:20]:20} | {status}")

# Analysis
print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

unique_qual = set(str(q) for q in qual_scores if q != 'N/A')
unique_fit = set(str(f) for f in fit_scores if f != 'N/A')

print(f"\nUnique qualification scores: {unique_qual}")
print(f"Unique fit scores: {unique_fit}")

if len(unique_qual) == 1:
    the_score = list(unique_qual)[0]
    print(f"\n🔴 [PROBLEM] ALL {len(hottest)} leads have IDENTICAL qualification score: {the_score}")
    print("    This means qualification scoring is BROKEN or using a hardcoded default")
    print("    Real qualification should vary based on:")
    print("      - Pain signals")
    print("      - Company compliance burden")
    print("      - Decision maker accessibility")
    print("      - Procurement authority")
elif len(unique_qual) < 3:
    print(f"\n🟡 [WARNING] Only {len(unique_qual)} different scores across {len(hottest)} leads")
    print("    Qualification may not be differentiating well")
else:
    print(f"\n✅ [OK] Scores vary appropriately ({len(unique_qual)} unique values)")

# Detailed look at one target
if hottest:
    print("\n" + "=" * 80)
    print("DETAILED SAMPLE (first target)")
    print("=" * 80)
    target = hottest[0]
    print(json.dumps(target, indent=2))

print("\n" + "=" * 80)
