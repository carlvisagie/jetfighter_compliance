"""Audit projects for test data patterns (PATCH identifiers)."""
import json
from pathlib import Path
from collections import defaultdict

def audit_projects():
    projects_dir = Path("data/projects")
    if not projects_dir.exists():
        print("No projects directory found")
        return
    
    project_dirs = [p for p in projects_dir.iterdir() if p.is_dir()]
    print(f"Total project directories: {len(project_dirs)}\n")
    
    test_indicators = {
        "patch_prefix": [],
        "test_email": [],
        "demo_ids": [],
        "production": []
    }
    
    for proj_dir in sorted(project_dirs):
        meta_file = proj_dir / "meta.json"
        if not meta_file.exists():
            continue
            
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            project_id = data.get("project_id", proj_dir.name)
            customer_name = data.get("customer", {}).get("name", "N/A")
            customer_email = data.get("customer", {}).get("email", "N/A")
            status = data.get("status", "unknown")
            
            # Classify entry
            is_test = False
            reasons = []
            
            if customer_name and ("PATCH" in customer_name.upper() or "patch" in customer_name):
                test_indicators["patch_prefix"].append((project_id, customer_name, customer_email, status))
                is_test = True
                reasons.append("PATCH in name")
            
            if "@test." in customer_email or customer_email.startswith("test@"):
                test_indicators["test_email"].append((project_id, customer_name, customer_email, status))
                is_test = True
                reasons.append("test email")
            
            if "verify" in customer_email and ("@test" in customer_email or "13a4" in customer_email.lower()):
                if (project_id, customer_name, customer_email, status) not in test_indicators["test_email"]:
                    test_indicators["test_email"].append((project_id, customer_name, customer_email, status))
                is_test = True
                if "verify test pattern" not in reasons:
                    reasons.append("verify test pattern")
            
            # Check for demo/test project IDs
            if any(x in project_id.upper() for x in ["DEMO", "TEST", "VIODEMO"]):
                test_indicators["demo_ids"].append((project_id, customer_name, customer_email, status))
                is_test = True
                if "demo/test ID" not in reasons:
                    reasons.append("demo/test ID")
            
            if not is_test:
                test_indicators["production"].append((project_id, customer_name, customer_email, status))
            
            # Print entry
            status_label = "TEST" if is_test else "PROD"
            reason_str = f" ({', '.join(reasons)})" if reasons else ""
            print(f"[{status_label}] {project_id}")
            print(f"      Customer: {customer_name}")
            print(f"      Email: {customer_email}")
            print(f"      Status: {status}{reason_str}\n")
            
        except Exception as e:
            print(f"Error reading {meta_file}: {e}")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"PATCH prefix in name: {len(test_indicators['patch_prefix'])}")
    print(f"Test email domains: {len(test_indicators['test_email'])}")
    print(f"Demo/Test IDs: {len(test_indicators['demo_ids'])}")
    print(f"Production entries: {len(test_indicators['production'])}")
    
    # Calculate unique test entries (some may be in multiple categories)
    all_test_ids = set()
    for category in ['patch_prefix', 'test_email', 'demo_ids']:
        all_test_ids.update(entry[0] for entry in test_indicators[category])
    
    print(f"\nTotal unique test projects: {len(all_test_ids)}")
    print(f"Total production projects: {len(test_indicators['production'])}")
    
    return test_indicators

if __name__ == "__main__":
    audit_projects()
