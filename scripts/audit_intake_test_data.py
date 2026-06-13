"""Audit intake queue for test data vs production data."""
import json
from pathlib import Path
from collections import defaultdict

def audit_intake_queue():
    intake_dir = Path("data/intakes")
    if not intake_dir.exists():
        print("No intakes directory found")
        return
    
    intakes = list(intake_dir.glob("*/intake.json"))
    print(f"Total intake entries: {len(intakes)}\n")
    
    test_indicators = {
        "patch_prefix": [],
        "test_email": [],
        "test_artifact": [],
        "production": []
    }
    
    for intake_path in sorted(intakes):
        try:
            data = json.loads(intake_path.read_text(encoding="utf-8"))
            intake_id = data.get("intake_id", "unknown")
            customer_name = data.get("customer_name", "N/A")
            customer_email = data.get("customer_email", "N/A")
            
            # Classify entry
            is_test = False
            reasons = []
            
            if customer_name and ("PATCH" in customer_name.upper() or "patch" in customer_name):
                test_indicators["patch_prefix"].append((intake_id, customer_name, customer_email))
                is_test = True
                reasons.append("PATCH in name")
            
            if "@test." in customer_email or customer_email.startswith("test@"):
                test_indicators["test_email"].append((intake_id, customer_name, customer_email))
                is_test = True
                reasons.append("test email")
            
            # Check for verify patterns common in test data
            if "verify" in customer_email and ("@test" in customer_email or "13a4" in customer_email.lower()):
                if (intake_id, customer_name, customer_email) not in test_indicators["test_email"]:
                    test_indicators["test_email"].append((intake_id, customer_name, customer_email))
                is_test = True
                if "verify email" not in reasons:
                    reasons.append("verify test pattern")
            
            if not is_test:
                test_indicators["production"].append((intake_id, customer_name, customer_email))
            
            # Print entry
            status = "TEST" if is_test else "PROD"
            reason_str = f" ({', '.join(reasons)})" if reasons else ""
            print(f"[{status}] {intake_id}: {customer_name} - {customer_email}{reason_str}")
            
        except Exception as e:
            print(f"Error reading {intake_path}: {e}")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"PATCH prefix in name: {len(test_indicators['patch_prefix'])}")
    print(f"Test email domains: {len(test_indicators['test_email'])}")
    print(f"Production entries: {len(test_indicators['production'])}")
    print(f"\nTotal test entries: {len(test_indicators['patch_prefix']) + len(test_indicators['test_email'])}")
    print(f"Total production entries: {len(test_indicators['production'])}")
    
    return test_indicators

if __name__ == "__main__":
    audit_intake_queue()
