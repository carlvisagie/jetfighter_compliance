"""Search for intakes with PATCH in company name."""
import json
from pathlib import Path

intakes_dir = Path("data/intakes")
patch_intakes = []

for intake_dir in intakes_dir.glob("FB-*"):
    intake_json = intake_dir / "intake.json"
    if not intake_json.exists():
        continue
    
    try:
        data = json.loads(intake_json.read_text(encoding="utf-8"))
        company = data.get("company", "")
        email = data.get("email", "")
        
        if "PATCH" in company.upper() or "patch" in company:
            patch_intakes.append({
                "intake_id": intake_dir.name,
                "company": company,
                "email": email,
                "status": data.get("review_status") or data.get("status", "unknown")
            })
    except Exception as e:
        print(f"Error reading {intake_json}: {e}")

print(f"Found {len(patch_intakes)} intakes with PATCH in company name:")
for p in patch_intakes[:30]:
    print(f"  {p['intake_id']}: {p['company']} ({p['email']}) [{p['status']}]")

if not patch_intakes:
    print("\nNo PATCH identifiers found in current intake data.")
    print("This suggests the screenshots may be from an earlier state,")
    print("or the issue is in how the UI is rendering/caching data.")
