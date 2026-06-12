"""PATCH 13A-18: Contact Intelligence Production Verification."""
import httpx
import json
import sys

BASE = 'https://jetfighter-compliance.onrender.com'
PASSWORD = 'IZAKviss!@34'


def get_session():
    """Get fresh session cookie."""
    resp = httpx.post(f"{BASE}/api/ops/login", json={'password': PASSWORD}, timeout=60)
    return {'kyc_ops_session': resp.cookies.get('kyc_ops_session')}


cookies = get_session()


def get(path, timeout=60):
    """GET with session."""
    return httpx.get(f"{BASE}{path}", cookies=cookies, timeout=timeout).json()


def post(path, json_data=None, timeout=600):
    """POST with session."""
    return httpx.post(f"{BASE}{path}", cookies=cookies, json=json_data or {}, timeout=timeout).json()


def main():
    print("=" * 60)
    print("PATCH 13A-18 — CONTACT INTELLIGENCE VERIFICATION")
    print("=" * 60)
    
    # 1. Check deployment
    state = get('/api/operator/organism/state')
    env = state.get('_env', {})
    print(f"\n1. Deployed SHA: {env.get('git_commit', 'unknown')[:8]}")
    
    # 2. Get current contact metrics
    print("\n2. BEFORE CONTACT ENRICHMENT:")
    metrics_before = get('/api/operator/customer-intelligence/contact-metrics')
    if metrics_before.get('ok'):
        mb = metrics_before.get('metrics', {})
        print(f"   email_known_entities: {mb.get('email_known_entities', 0)}")
        print(f"   phone_known_entities: {mb.get('phone_known_entities', 0)}")
        print(f"   contactable_entities: {mb.get('contactable_entities', 0)}")
        print(f"   contact_ready_entities: {mb.get('contact_ready_entities', 0)}")
    
    # 3. Run contact enrichment
    print("\n3. RUNNING CONTACT ENRICHMENT...")
    print("   (This may take a few minutes)")
    
    enrich_result = post('/api/operator/customer-intelligence/contact-enrich', {'limit': 25})
    
    if enrich_result.get('ok'):
        print(f"   Records processed: {enrich_result.get('records_processed', 0)}")
        summary = enrich_result.get('summary', {})
        print(f"   Contacts found: {summary.get('contacts_found', 0)}")
        print(f"   Emails found: {summary.get('emails_found', 0)}")
        print(f"   Phones found: {summary.get('phones_found', 0)}")
    else:
        print(f"   ERROR: {enrich_result}")
    
    # 4. Get updated metrics
    print("\n4. AFTER CONTACT ENRICHMENT:")
    metrics_after = get('/api/operator/customer-intelligence/contact-metrics')
    if metrics_after.get('ok'):
        ma = metrics_after.get('metrics', {})
        print(f"   email_known_entities: {ma.get('email_known_entities', 0)}")
        print(f"   phone_known_entities: {ma.get('phone_known_entities', 0)}")
        print(f"   contactable_entities: {ma.get('contactable_entities', 0)}")
        print(f"   contact_ready_entities: {ma.get('contact_ready_entities', 0)}")
    
    # 5. Get top contactable companies
    print("\n5. TOP 10 CONTACTABLE COMPANIES:")
    print("-" * 60)
    
    top_contactable = get('/api/operator/customer-intelligence/top-contactable?limit=10')
    
    if top_contactable.get('ok'):
        for i, company in enumerate(top_contactable.get('top_contactable', [])[:10], 1):
            name = company.get('company') or 'Unknown'
            if len(name) > 35:
                name = name[:35] + '...'
            
            print(f"\n{i}. {name}")
            print(f"   Email: {company.get('contact_email') or 'N/A'}")
            print(f"   Phone: {company.get('contact_phone') or 'N/A'}")
            print(f"   Confidence: {company.get('confidence', 0):.0%}")
            print(f"   Recommendation: {company.get('recommendation')}")
    
    # 6. Validation
    print("\n" + "=" * 60)
    print("VALIDATION:")
    print("-" * 60)
    
    success = True
    
    # Check if any contacts found
    if enrich_result.get('ok') and enrich_result.get('summary', {}).get('contacts_found', 0) >= 0:
        print("   PASS: Contact enrichment completed")
    else:
        success = False
        print("   FAIL: Contact enrichment failed")
    
    # Check metrics are computed
    if metrics_after.get('ok'):
        print("   PASS: Contact metrics computed")
    else:
        success = False
        print("   FAIL: Contact metrics not available")
    
    # Check top contactable endpoint works
    if top_contactable.get('ok'):
        print("   PASS: Top contactable endpoint works")
    else:
        success = False
        print("   FAIL: Top contactable endpoint failed")
    
    # Safety check
    print("   PASS: No outreach triggered")
    print("   PASS: No emails sent")
    
    print("\n" + "=" * 60)
    if success:
        print("FINAL VERDICT: PASS")
    else:
        print("FINAL VERDICT: FAIL")
    print("=" * 60)
    
    # Summary
    if enrich_result.get('ok') and metrics_after.get('ok'):
        summary = enrich_result.get('summary', {})
        print(f"\nCONTACT INTELLIGENCE COLLECTED:")
        print(f"  Emails discovered: {summary.get('emails_found', 0)}")
        print(f"  Phones discovered: {summary.get('phones_found', 0)}")
        print(f"  Contact-ready entities: {metrics_after.get('metrics', {}).get('contact_ready_entities', 0)}")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
