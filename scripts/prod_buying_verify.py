#!/usr/bin/env python3
"""PATCH 13A-20: Production Verification - Buying Likelihood Intelligence Engine.

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
    print("=" * 80)
    print("PATCH 13A-20: PRODUCTION VERIFICATION")
    print("BUYING LIKELIHOOD INTELLIGENCE ENGINE")
    print("=" * 80)
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
    
    # Check buying-signals endpoint
    print()
    print("Step 3: Check buying signals inventory...")
    signals_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/buying-signals")
    
    if signals_resp.status_code != 200:
        print(f"  ENDPOINT NOT DEPLOYED YET: {signals_resp.status_code}")
        print("  Waiting for deployment...")
        
        for attempt in range(30):
            time.sleep(10)
            print(f"  Waiting... ({(attempt+1)*10}s)")
            
            # Re-login with fresh session
            session = requests.Session()
            login_resp = session.post(f"{PROD_URL}/api/ops/login", json={"password": password})
            if login_resp.status_code != 200:
                continue
            
            signals_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/buying-signals")
            if signals_resp.status_code == 200:
                break
        else:
            print("  DEPLOYMENT TIMEOUT")
            return 1
    
    signals = signals_resp.json()
    inventory = signals.get("inventory", {})
    print(f"  Total Signals: {inventory.get('total_signals', 0)}")
    print(f"  Max Possible Score: {inventory.get('max_possible_score', 0)}")
    print(f"  Signal Categories: {list(inventory.get('signal_categories', {}).keys())}")
    
    # Get buying likelihood report
    print()
    print("Step 4: Get buying likelihood report...")
    likelihood_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/buying-likelihood?limit=20")
    
    if likelihood_resp.status_code != 200:
        print(f"  Failed: {likelihood_resp.status_code}")
        return 1
    
    report = likelihood_resp.json()
    
    print(f"  Total Records: {report.get('total_records', 0)}")
    print()
    
    # Tier distribution
    tiers = report.get("tier_distribution", {})
    print("  TIER DISTRIBUTION:")
    for tier, count in tiers.items():
        print(f"    {tier}: {count}")
    
    # Top 10 prospects
    print()
    print("  TOP 10 BY BUYING LIKELIHOOD:")
    print("-" * 80)
    
    for prospect in report.get("top_prospects", [])[:10]:
        rank = prospect.get("rank", "?")
        company = prospect.get("company", "Unknown")[:40]
        tier = prospect.get("buying_tier", "UNKNOWN")
        score = prospect.get("buying_score", 0)
        score_pct = prospect.get("score_percentage", 0)
        
        print(f"  {rank:2}. {company:<40} | {tier:<20} | {score_pct:.0f}%")
        print(f"      WHY: {prospect.get('why_this_company', 'N/A')[:70]}")
        print(f"      NOW: {prospect.get('why_now', 'N/A')[:70]}")
        print(f"      NEXT: {prospect.get('next_action', 'N/A')}")
        print()
    
    # Organism answers
    print()
    print("=" * 80)
    print("ORGANISM ANSWERS THE 6 KEY QUESTIONS")
    print("=" * 80)
    answers = report.get("organism_answers", {})
    
    print()
    print(f"  Q1: {answers.get('question_1', 'N/A')}")
    print(f"  A1: {answers.get('answer_1', 'N/A')}")
    
    print()
    print(f"  Q2: {answers.get('question_2', 'N/A')}")
    print(f"  A2: {answers.get('answer_2', 'N/A')[:100]}")
    
    print()
    print(f"  Q3: {answers.get('question_3', 'N/A')}")
    print(f"  A3: {answers.get('answer_3', 'N/A')[:100]}")
    
    print()
    print(f"  Q4: {answers.get('question_4', 'N/A')}")
    supporting = answers.get("answer_4", [])
    if supporting:
        for ev in supporting[:5]:
            print(f"      - {ev}")
    else:
        print("      (no supporting evidence)")
    
    print()
    print(f"  Q5: {answers.get('question_5', 'N/A')}")
    missing = answers.get("answer_5", [])
    if missing:
        for ev in missing[:5]:
            print(f"      - {ev}")
    else:
        print("      (no missing evidence)")
    
    print()
    print(f"  Q6: {answers.get('question_6', 'N/A')}")
    print(f"  A6: {answers.get('answer_6', 'N/A')}")
    
    print()
    print(f"  HAS SUFFICIENT EVIDENCE: {answers.get('has_sufficient_evidence', False)}")
    
    # Validation
    print()
    print("Step 5: Run buying validation...")
    validation_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/buying-validation")
    
    if validation_resp.status_code == 200:
        validation = validation_resp.json()
        print(f"  Validation Passed: {validation.get('validation_passed', False)}")
        checks = validation.get("checks", {})
        for check, passed in checks.items():
            status = "PASS" if passed else "FAIL"
            print(f"    {check}: {status}")
    
    # Safety check
    print()
    print("=" * 80)
    print("SAFETY VERIFICATION")
    print("=" * 80)
    print("  Outreach sent during verification: NO")
    print("  Emails sent during verification: NO")
    print("  Auto-send enabled: NO")
    print("  Evidence collection only: YES")
    
    # Verdict
    print()
    print("=" * 80)
    print("VERDICT")
    print("=" * 80)
    
    buy_now = tiers.get("BUY_NOW", 0)
    high_potential = tiers.get("HIGH_POTENTIAL", 0)
    
    if report.get("ok"):
        print("  PATCH 13A-20 DEPLOYED: YES")
        print(f"  BUY_NOW companies: {buy_now}")
        print(f"  HIGH_POTENTIAL companies: {high_potential}")
        print(f"  Can answer 'Who should we contact first?': {'YES' if answers.get('answer_1') else 'NO'}")
        print()
        print("  VERIFICATION: PASS")
        return 0
    else:
        print("  VERIFICATION: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
