"""Analyze all remaining intakes for test data patterns."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("PRODUCTION INTAKE QUEUE ANALYSIS")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/operator/intake/queue")
    r.raise_for_status()
    data = r.json()
    
    queue = data.get('queue', [])
    print(f"\nTotal intakes: {len(queue)}\n")
    
    # Analyze each intake
    test_patterns = []
    real_patterns = []
    
    for entry in queue:
        intake_id = entry.get('intake_id', '')
        company = entry.get('company', '')
        email = entry.get('email', '')
        status = entry.get('review_status', '')
        uploaded = entry.get('uploaded_at', '')
        
        # Check for test indicators
        is_test = False
        reasons = []
        
        if not company or company.strip() == '':
            is_test = True
            reasons.append("EMPTY_COMPANY")
        
        if 'test' in company.lower():
            is_test = True
            reasons.append("TEST_IN_NAME")
        
        if 'aegis' in company.lower() and '13a4' in company.lower():
            is_test = True
            reasons.append("AEGIS_13A4_PATTERN")
        
        if 'verify' in company.lower() and ('2026' in company or '13a4' in company.lower()):
            is_test = True
            reasons.append("VERIFY_DATE_PATTERN")
        
        if not email or '@' not in email:
            is_test = True
            reasons.append("MISSING_EMAIL")
        
        entry_info = {
            'intake_id': intake_id,
            'company': company or '(empty)',
            'email': email or '(none)',
            'status': status,
            'uploaded_at': uploaded[:10] if uploaded else '(none)',
            'reasons': reasons
        }
        
        if is_test:
            test_patterns.append(entry_info)
        else:
            real_patterns.append(entry_info)
    
    print("=" * 80)
    print(f"TEST DATA CANDIDATES ({len(test_patterns)})")
    print("=" * 80)
    
    for entry in test_patterns:
        print(f"\n{entry['intake_id']}")
        print(f"  Company: {entry['company']}")
        print(f"  Email: {entry['email']}")
        print(f"  Status: {entry['status']}")
        print(f"  Uploaded: {entry['uploaded_at']}")
        print(f"  Test Indicators: {', '.join(entry['reasons'])}")
    
    print("\n" + "=" * 80)
    print(f"LIKELY REAL CUSTOMERS ({len(real_patterns)})")
    print("=" * 80)
    
    for entry in real_patterns:
        print(f"\n{entry['intake_id']}")
        print(f"  Company: {entry['company']}")
        print(f"  Email: {entry['email']}")
        print(f"  Status: {entry['status']}")
        print(f"  Uploaded: {entry['uploaded_at']}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total intakes: {len(queue)}")
    print(f"Test data candidates: {len(test_patterns)}")
    print(f"Likely real customers: {len(real_patterns)}")
    
    if test_patterns:
        print(f"\nACTION NEEDED: Archive {len(test_patterns)} test data intakes")
    else:
        print("\nQueue is clean!")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
