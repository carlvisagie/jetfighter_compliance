"""PATCH 13A-17: Production deep enrichment verification script."""
import httpx
import json
import sys

# Session from login
session_cookie = 'eyJyb2xlIjoib3BzIiwidHMiOjE3ODEyNDM2MzF9.aiue7w.W5PQO2ZULScKlj-ekUkB0gnquic'
cookies = {'kyc_ops_session': session_cookie}
BASE = 'https://jetfighter-compliance.onrender.com'


def get(path, **kwargs):
    """GET with session."""
    return httpx.get(f"{BASE}{path}", cookies=cookies, timeout=60, **kwargs).json()


def post(path, json_data=None, **kwargs):
    """POST with session."""
    return httpx.post(f"{BASE}{path}", cookies=cookies, json=json_data or {}, timeout=300, **kwargs).json()


def check_cockpit():
    """Check cockpit view."""
    data = get('/api/operator/customer-intelligence/cockpit')
    print('=== COCKPIT VIEW ===')
    print(f"total_records: {data.get('total_records')}")
    print(f"average_completeness: {data.get('average_completeness')}")
    print()
    print('TOP 5 PROSPECTS:')
    for p in data.get('top_prospects', [])[:5]:
        name = p.get('company_name', 'unknown')
        if len(name) > 50:
            name = name[:50] + '...'
        print(f"  {name}")
        print(f"    completeness: {p.get('completeness')}%")
        print(f"    known: {p.get('known_fields', [])}")
    return data


def check_top_prospects():
    """Check top prospects."""
    data = get('/api/operator/top-prospects')
    print('=== TOP PROSPECTS ===')
    print(f"total_prospects: {data.get('total_prospects')}")
    
    prospects = data.get('prospects', [])
    if prospects:
        completeness_values = [p.get('completeness', 0) for p in prospects]
        avg = sum(completeness_values) / len(completeness_values)
        print(f"average_completeness: {avg:.1f}%")
        
        tiers = {}
        for p in prospects:
            tier = p.get('tier', 'unknown')
            tiers[tier] = tiers.get(tier, 0) + 1
        print(f"tier_distribution: {tiers}")
    return data


def check_sample_record():
    """Check a sample record for debugging."""
    data = get('/api/operator/customer-intelligence')
    records = data.get('records', [])
    if not records:
        print("No records found")
        return
    
    # Get first record ID
    first = records[0]
    record_id = first.get('record_id')
    if not record_id:
        print("No record_id found")
        return
    
    print(f"\n=== SAMPLE RECORD: {record_id} ===")
    print(f"company_name: {first.get('company_name', {}).get('value', 'unknown')}")
    
    # Check UEI
    uei = first.get('uei', {})
    print(f"uei.value: {uei.get('value')}")
    print(f"uei.state: {uei.get('state')}")
    
    # Check contract value
    cv = first.get('contract_value', {})
    print(f"contract_value.value: {cv.get('value')}")
    print(f"contract_value.state: {cv.get('state')}")


def run_deep_enrich_single(record_id):
    """Run deep enrichment on a single record."""
    print(f"\n=== DEEP ENRICH SINGLE: {record_id} ===")
    data = post(f'/api/operator/customer-intelligence/deep-enrich/{record_id}')
    print(json.dumps(data, indent=2))
    return data


def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else ['check']
    
    if 'check' in args:
        check_top_prospects()
        print()
        check_cockpit()
        check_sample_record()
    
    if 'enrich' in args:
        # Get a record ID and enrich it
        data = get('/api/operator/customer-intelligence')
        records = data.get('records', [])
        if records:
            record_id = records[0].get('record_id')
            run_deep_enrich_single(record_id)


if __name__ == '__main__':
    main()
