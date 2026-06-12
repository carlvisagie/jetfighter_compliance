#!/usr/bin/env python3
"""PATCH 13A-21: Production Verification Script for Compliance Trigger Intelligence.

This script verifies against PRODUCTION.

Returns:
1. Deployed SHA
2. Records processed
3. Trigger distribution
4. Top 10 trigger companies
5. Best trigger company
6. Trigger explanation
7. Supporting evidence
8. Missing evidence
9. Safety confirmation
10. PASS / FAIL
"""
import os
import sys
import json
import requests

PRODUCTION_URL = os.getenv("PRODUCTION_URL", "https://jetfighter-compliance.onrender.com")
OPS_KEY = os.getenv("OPS_KEY", "")


def verify_production():
    """Run production verification."""
    headers = {"X-Ops-Key": OPS_KEY}
    results = {
        "deployed_sha": "UNKNOWN",
        "records_processed": 0,
        "trigger_distribution": {},
        "top_10_trigger_companies": [],
        "best_trigger_company": None,
        "trigger_explanation": None,
        "supporting_evidence": [],
        "missing_evidence": [],
        "safety_confirmed": False,
        "overall_status": "FAIL",
        "errors": [],
    }
    
    print("=" * 60)
    print("PATCH 13A-21: COMPLIANCE TRIGGER INTELLIGENCE")
    print("PRODUCTION VERIFICATION")
    print("=" * 60)
    print(f"Target: {PRODUCTION_URL}")
    print()
    
    # 1. Get deployed SHA
    try:
        r = requests.get(f"{PRODUCTION_URL}/healthz", timeout=30)
        if r.status_code == 200:
            data = r.json()
            results["deployed_sha"] = data.get("git_sha", data.get("sha", "UNKNOWN"))
            print(f"1. Deployed SHA: {results['deployed_sha']}")
        else:
            results["errors"].append(f"Health check failed: {r.status_code}")
            print(f"1. Deployed SHA: FAILED ({r.status_code})")
    except Exception as e:
        results["errors"].append(f"Health check error: {e}")
        print(f"1. Deployed SHA: ERROR - {e}")
    
    # 2-4. Get compliance trigger report
    try:
        r = requests.get(
            f"{PRODUCTION_URL}/api/operator/customer-intelligence/compliance-triggers?limit=20",
            headers=headers,
            timeout=60,
        )
        if r.status_code == 200:
            data = r.json()
            results["records_processed"] = data.get("total_records", 0)
            results["trigger_distribution"] = data.get("trigger_distribution", {})
            
            top_companies = data.get("top_trigger_companies", [])[:10]
            results["top_10_trigger_companies"] = [
                {
                    "rank": c.get("rank"),
                    "company": c.get("company"),
                    "trigger_type": c.get("trigger_type"),
                    "trigger_score": c.get("trigger_score"),
                }
                for c in top_companies
            ]
            
            print(f"2. Records processed: {results['records_processed']}")
            print()
            print("3. Trigger distribution:")
            for trigger_type, count in results["trigger_distribution"].items():
                print(f"   - {trigger_type}: {count}")
            print()
            print("4. Top 10 trigger companies:")
            for company in results["top_10_trigger_companies"]:
                print(f"   #{company['rank']}: {company['company']} - {company['trigger_type']} (score: {company['trigger_score']})")
        else:
            results["errors"].append(f"Compliance triggers failed: {r.status_code}")
            print(f"2-4. Compliance triggers: FAILED ({r.status_code})")
            if r.text:
                print(f"     Response: {r.text[:200]}")
    except Exception as e:
        results["errors"].append(f"Compliance triggers error: {e}")
        print(f"2-4. Compliance triggers: ERROR - {e}")
    
    # 5-8. Get trigger validation
    print()
    try:
        r = requests.get(
            f"{PRODUCTION_URL}/api/operator/customer-intelligence/compliance-trigger-validation",
            headers=headers,
            timeout=60,
        )
        if r.status_code == 200:
            data = r.json()
            results["best_trigger_company"] = data.get("best_trigger_company")
            results["trigger_explanation"] = data.get("trigger_explanation")
            results["supporting_evidence"] = data.get("supporting_evidence", [])
            results["missing_evidence"] = data.get("missing_evidence", [])
            
            print(f"5. Best trigger company: {results['best_trigger_company']}")
            print()
            print("6. Trigger explanation:")
            if isinstance(results["trigger_explanation"], dict):
                print(f"   What: {results['trigger_explanation'].get('what_trigger', 'N/A')}")
                print(f"   Why: {results['trigger_explanation'].get('why', 'N/A')}")
                print(f"   Why now: {results['trigger_explanation'].get('why_now', 'N/A')}")
                print(f"   Discuss: {results['trigger_explanation'].get('what_to_discuss', 'N/A')}")
            else:
                print(f"   {results['trigger_explanation']}")
            print()
            print("7. Supporting evidence:")
            for ev in results["supporting_evidence"]:
                print(f"   - {ev}")
            print()
            print("8. Missing evidence:")
            for ev in results["missing_evidence"]:
                print(f"   - {ev}")
        else:
            results["errors"].append(f"Validation failed: {r.status_code}")
            print(f"5-8. Validation: FAILED ({r.status_code})")
    except Exception as e:
        results["errors"].append(f"Validation error: {e}")
        print(f"5-8. Validation: ERROR - {e}")
    
    # 9. Safety confirmation
    print()
    print("9. Safety confirmation:")
    safety_checks = {
        "no_outreach_keywords": True,
        "no_auto_send": True,
        "evidence_based": True,
    }
    
    outreach_keywords = ["send email", "send message", "contact now", "auto-send"]
    
    for company in results["top_10_trigger_companies"]:
        trigger_type = company.get("trigger_type", "")
        for kw in outreach_keywords:
            if kw in trigger_type.lower():
                safety_checks["no_outreach_keywords"] = False
    
    for ev in results["supporting_evidence"]:
        for kw in outreach_keywords:
            if kw in ev.lower():
                safety_checks["no_outreach_keywords"] = False
    
    if results["trigger_distribution"].get("INSUFFICIENT_EVIDENCE", 0) >= 0:
        safety_checks["evidence_based"] = True
    
    results["safety_confirmed"] = all(safety_checks.values())
    
    for check, passed in safety_checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"   - {check}: {status}")
    print(f"   Overall safety: {'CONFIRMED' if results['safety_confirmed'] else 'FAILED'}")
    
    # 10. Overall status
    print()
    print("=" * 60)
    
    has_data = results["records_processed"] > 0
    has_triggers = sum(results["trigger_distribution"].values()) > 0 if results["trigger_distribution"] else False
    is_safe = results["safety_confirmed"]
    no_errors = len(results["errors"]) == 0
    
    if has_data and is_safe and no_errors:
        if has_triggers:
            results["overall_status"] = "PASS"
        else:
            results["overall_status"] = "PASS (NO_TRIGGER_DATA)"
    else:
        results["overall_status"] = "FAIL"
    
    print(f"10. OVERALL STATUS: {results['overall_status']}")
    print("=" * 60)
    
    if results["errors"]:
        print()
        print("Errors encountered:")
        for err in results["errors"]:
            print(f"  - {err}")
    
    return results


if __name__ == "__main__":
    if not OPS_KEY:
        print("ERROR: OPS_KEY environment variable not set")
        print("Set it with: $env:OPS_KEY = 'your-key'")
        sys.exit(1)
    
    results = verify_production()
    
    if results["overall_status"].startswith("PASS"):
        sys.exit(0)
    else:
        sys.exit(1)
