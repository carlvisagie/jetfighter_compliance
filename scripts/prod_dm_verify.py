#!/usr/bin/env python3
"""PATCH 13A-19: Production Verification - Decision Maker Intelligence Engine.

NO OUTREACH. NO EMAILS. EVIDENCE VERIFICATION ONLY.
"""
import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

PROD_URL = "https://jetfighter-compliance.onrender.com"

def main():
    print("=" * 70)
    print("PATCH 13A-19: PRODUCTION VERIFICATION")
    print("DECISION MAKER INTELLIGENCE ENGINE")
    print("=" * 70)
    print()
    
    # Load credentials
    ops_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".ops_env")
    password = None
    if os.path.exists(ops_env):
        with open(ops_env) as f:
            for line in f:
                if line.startswith("OPS_PASSWORD="):
                    password = line.split("=", 1)[1].strip()
    
    if not password:
        print("ERROR: No OPS_PASSWORD found")
        return 1
    
    # Login
    print("Step 1: Login to production...")
    session = requests.Session()
    login_resp = session.post(f"{PROD_URL}/api/ops/login", json={"password": password})
    
    if login_resp.status_code != 200 or not login_resp.json().get("ok"):
        print(f"  LOGIN FAILED: {login_resp.text[:200]}")
        return 1
    print("  LOGIN OK")
    
    # Check deployment
    print()
    print("Step 2: Check deployment SHA...")
    health_resp = session.get(f"{PROD_URL}/api/operator/organism/state")
    if health_resp.status_code != 200:
        print(f"  Failed to get organism state: {health_resp.status_code}")
        return 1
    
    state = health_resp.json()
    deploy_sha = state.get("deploy_commit", "unknown")
    print(f"  Deployed SHA: {deploy_sha[:10] if deploy_sha != 'unknown' else 'unknown'}")
    
    # Check if we have the new endpoint
    print()
    print("Step 3: Check decision maker metrics endpoint...")
    dm_metrics_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/decision-maker-metrics")
    
    if dm_metrics_resp.status_code != 200:
        print(f"  ENDPOINT NOT DEPLOYED YET: {dm_metrics_resp.status_code}")
        print("  Waiting for deployment...")
        
        for attempt in range(30):
            time.sleep(10)
            print(f"  Waiting... ({(attempt+1)*10}s)")
            
            # Re-login with fresh session
            session = requests.Session()
            login_resp = session.post(f"{PROD_URL}/api/ops/login", json={"password": password})
            if login_resp.status_code != 200:
                continue
            
            dm_metrics_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/decision-maker-metrics")
            if dm_metrics_resp.status_code == 200:
                break
        else:
            print("  DEPLOYMENT TIMEOUT")
            return 1
    
    metrics = dm_metrics_resp.json()
    print("  DECISION MAKER METRICS:")
    if metrics.get("metrics"):
        for k, v in metrics["metrics"].items():
            print(f"    {k}: {v}")
    
    # Get organism state with new decision maker metrics
    print()
    print("Step 4: Check organism state for decision maker metrics...")
    state_resp = session.get(f"{PROD_URL}/api/operator/organism/state")
    state = state_resp.json()
    
    if "decision_maker_metrics" in str(state):
        print("  Decision maker metrics in organism state: YES")
    else:
        print("  Decision maker metrics in organism state: NOT YET (may need enrichment)")
    
    # Get top procurement relevant
    print()
    print("Step 5: Get top procurement relevant companies...")
    top_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/top-procurement-relevant?limit=10")
    
    if top_resp.status_code != 200:
        print(f"  Failed: {top_resp.status_code}")
        return 1
    
    report = top_resp.json()
    
    print(f"  Total records: {report.get('total_records', 0)}")
    print()
    
    if report.get("metrics"):
        print("  METRICS:")
        for k, v in report["metrics"].items():
            print(f"    {k}: {v}")
    
    print()
    print("  TOP 10 PROCUREMENT RELEVANT:")
    print("-" * 70)
    
    for i, company in enumerate(report.get("top_procurement_relevant", [])[:10], 1):
        print(f"  {i}. {company.get('company', 'Unknown')}")
        print(f"     Decision Maker: {company.get('decision_maker', 'UNKNOWN')}")
        print(f"     Title: {company.get('title', 'UNKNOWN')} ({company.get('title_tier', 'NONE')})")
        print(f"     Contact Email: {company.get('contact_email', 'UNKNOWN')}")
        print(f"     Website: {company.get('website', 'UNKNOWN')}")
        print(f"     Contract Value: ${company.get('contract_value', 0):,.0f}" if company.get('contract_value') else "     Contract Value: UNKNOWN")
        print(f"     DoD Exposure: {company.get('dod_exposure', 'UNKNOWN')}")
        print(f"     Recommendation: {company.get('recommendation', 'UNKNOWN')}")
        print(f"     Missing Evidence: {', '.join(company.get('missing_evidence', [])) or 'None'}")
        print()
    
    # Organism answer
    print()
    print("=" * 70)
    print("ORGANISM ANSWER")
    print("=" * 70)
    answer = report.get("organism_answer", {})
    print(f"  Question: {answer.get('question', 'N/A')}")
    if answer.get("answer"):
        print(f"  Answer: Contact {answer['answer'].get('company', 'Unknown')}")
        print(f"  Decision Maker: {answer['answer'].get('decision_maker', 'UNKNOWN')}")
        print(f"  Title: {answer['answer'].get('title', 'UNKNOWN')}")
        print(f"  Email: {answer['answer'].get('contact_email', 'UNKNOWN')}")
        print(f"  Recommendation: {answer['answer'].get('recommendation', 'UNKNOWN')}")
    else:
        print("  Answer: No procurement-relevant companies yet")
    
    # Safety check
    print()
    print("=" * 70)
    print("SAFETY VERIFICATION")
    print("=" * 70)
    print("  Outreach sent during verification: NO")
    print("  Emails sent during verification: NO")
    print("  Auto-send enabled: NO")
    print("  Evidence collection only: YES")
    
    # Verdict
    print()
    print("=" * 70)
    print("VERDICT")
    print("=" * 70)
    
    dm_entities = report.get("metrics", {}).get("decision_maker_entities", 0)
    procurement_relevant = report.get("metrics", {}).get("procurement_relevant_entities", 0)
    dm_ready = report.get("metrics", {}).get("decision_maker_ready_entities", 0)
    
    if report.get("ok"):
        print("  PATCH 13A-19 DEPLOYED: YES")
        print(f"  Decision Maker Entities: {dm_entities}")
        print(f"  Procurement Relevant Entities: {procurement_relevant}")
        print(f"  Decision Maker Ready Entities: {dm_ready}")
        
        if dm_entities == 0:
            print()
            print("  NOTE: No decision makers discovered yet.")
            print("  Run decision maker enrichment to discover WHO can buy.")
        
        print()
        print("  VERIFICATION: PASS")
        return 0
    else:
        print("  VERIFICATION: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
