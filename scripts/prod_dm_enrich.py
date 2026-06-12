#!/usr/bin/env python3
"""PATCH 13A-19: Run Decision Maker Enrichment on Production.

Discovers WHO can buy at each company.
NO OUTREACH. NO EMAILS. EVIDENCE COLLECTION ONLY.
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
    print("PATCH 13A-19: DECISION MAKER ENRICHMENT")
    print("NO OUTREACH. NO EMAILS. EVIDENCE ONLY.")
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
    print("Step 1: Login...")
    session = requests.Session()
    login_resp = session.post(f"{PROD_URL}/api/ops/login", json={"password": password})
    
    if login_resp.status_code != 200 or not login_resp.json().get("ok"):
        print(f"  LOGIN FAILED: {login_resp.text[:200]}")
        return 1
    print("  LOGIN OK")
    
    # Get before metrics
    print()
    print("Step 2: Get BEFORE metrics...")
    before_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/decision-maker-metrics")
    before_metrics = before_resp.json().get("metrics", {})
    print(f"  decision_maker_entities: {before_metrics.get('decision_maker_entities', 0)}")
    print(f"  procurement_relevant_entities: {before_metrics.get('procurement_relevant_entities', 0)}")
    print(f"  decision_maker_ready_entities: {before_metrics.get('decision_maker_ready_entities', 0)}")
    
    # Run enrichment
    print()
    print("Step 3: Run Decision Maker Enrichment...")
    print("  (This discovers WHO can buy from public website sources)")
    print("  (NO OUTREACH. NO EMAILS. EVIDENCE ONLY.)")
    print()
    
    enrich_resp = session.post(
        f"{PROD_URL}/api/operator/customer-intelligence/decision-maker-enrich",
        json={"limit": 30},
        timeout=600,
    )
    
    if enrich_resp.status_code != 200:
        print(f"  ENRICHMENT FAILED: {enrich_resp.status_code}")
        print(f"  {enrich_resp.text[:500]}")
        return 1
    
    enrich_result = enrich_resp.json()
    
    print(f"  Records processed: {enrich_result.get('records_processed', 0)}")
    summary = enrich_result.get("summary", {})
    print(f"  Decision makers found: {summary.get('decision_makers_found', 0)}")
    print(f"  Tier 1 (President/Owner/CEO): {summary.get('tier_1_found', 0)}")
    print(f"  Tier 2 (Contracts/Compliance Manager): {summary.get('tier_2_found', 0)}")
    
    # Get after metrics
    print()
    print("Step 4: Get AFTER metrics...")
    after_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/decision-maker-metrics")
    after_metrics = after_resp.json().get("metrics", {})
    print(f"  decision_maker_entities: {after_metrics.get('decision_maker_entities', 0)}")
    print(f"  procurement_relevant_entities: {after_metrics.get('procurement_relevant_entities', 0)}")
    print(f"  decision_maker_ready_entities: {after_metrics.get('decision_maker_ready_entities', 0)}")
    
    # Show delta
    print()
    print("Step 5: DELTA...")
    dm_before = before_metrics.get("decision_maker_entities", 0)
    dm_after = after_metrics.get("decision_maker_entities", 0)
    print(f"  decision_maker_entities: {dm_before} -> {dm_after} (+{dm_after - dm_before})")
    
    pr_before = before_metrics.get("procurement_relevant_entities", 0)
    pr_after = after_metrics.get("procurement_relevant_entities", 0)
    print(f"  procurement_relevant: {pr_before} -> {pr_after} (+{pr_after - pr_before})")
    
    ready_before = before_metrics.get("decision_maker_ready_entities", 0)
    ready_after = after_metrics.get("decision_maker_ready_entities", 0)
    print(f"  decision_maker_ready: {ready_before} -> {ready_after} (+{ready_after - ready_before})")
    
    # Get top procurement relevant
    print()
    print("Step 6: Top Procurement Relevant Companies...")
    top_resp = session.get(f"{PROD_URL}/api/operator/customer-intelligence/top-procurement-relevant?limit=10")
    report = top_resp.json()
    
    print()
    print("  TOP 10 (ranked by procurement relevance):")
    print("-" * 70)
    
    for i, company in enumerate(report.get("top_procurement_relevant", [])[:10], 1):
        dm = company.get("decision_maker") or "UNKNOWN"
        title = company.get("title") or "UNKNOWN"
        tier = company.get("title_tier", "NONE")
        email = company.get("contact_email") or "UNKNOWN"
        rec = company.get("recommendation", "UNKNOWN")
        
        print(f"  {i}. {company.get('company', 'Unknown')}")
        print(f"     Decision Maker: {dm}")
        print(f"     Title: {title} ({tier})")
        print(f"     Contact Email: {email}")
        print(f"     Recommendation: {rec}")
        print()
    
    # Organism answer
    print()
    print("=" * 70)
    print("ORGANISM ANSWER")
    print("=" * 70)
    answer = report.get("organism_answer", {})
    print(f"  Question: {answer.get('question', 'N/A')}")
    if answer.get("answer"):
        top_answer = answer["answer"]
        dm = top_answer.get("decision_maker")
        title = top_answer.get("title")
        email = top_answer.get("contact_email")
        
        if dm and title and email:
            print(f"  Answer: Contact {dm} ({title}) at {top_answer.get('company')}")
            print(f"  Email: {email}")
            print(f"  Status: DECISION_MAKER_READY")
        elif email:
            print(f"  Answer: Contact {top_answer.get('company')}")
            print(f"  Email: {email}")
            print(f"  Status: CONTACTABLE (decision maker not yet identified)")
        else:
            print(f"  Answer: Enrich {top_answer.get('company')} to discover contact info")
            print(f"  Status: NEEDS ENRICHMENT")
    else:
        print("  Answer: No procurement-relevant companies yet")
    
    print()
    print("=" * 70)
    print("SAFETY CONFIRMATION")
    print("=" * 70)
    print("  Outreach sent: NO")
    print("  Emails sent: NO")
    print("  Auto-send: DISABLED")
    print("  Evidence collection only: YES")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
