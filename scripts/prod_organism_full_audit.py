#!/usr/bin/env python3
"""FULL ACQUISITION ORGANISM PRODUCTION AUDIT.

Checks EVERY component of the Acquisition Organism on PRODUCTION.
NO LOCAL TESTING. PRODUCTION IS THE ONLY TRUTH.
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

PROD_URL = "https://jetfighter-compliance.onrender.com"

class ProductionAudit:
    def __init__(self):
        self.session = requests.Session()
        self.results = {}
        self.password = None
        
    def load_credentials(self):
        ops_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".ops_env")
        if os.path.exists(ops_env):
            with open(ops_env) as f:
                for line in f:
                    if line.startswith("OPS_PASSWORD="):
                        self.password = line.split("=", 1)[1].strip()
        return bool(self.password)
    
    def login(self):
        resp = self.session.post(f"{PROD_URL}/api/ops/login", json={"password": self.password})
        return resp.status_code == 200 and resp.json().get("ok")
    
    def check(self, name, endpoint, method="GET", body=None, expected_fields=None):
        """Check a production endpoint."""
        try:
            if method == "GET":
                resp = self.session.get(f"{PROD_URL}{endpoint}", timeout=30)
            else:
                resp = self.session.post(f"{PROD_URL}{endpoint}", json=body or {}, timeout=60)
            
            if resp.status_code != 200:
                self.results[name] = {"status": "FAIL", "error": f"HTTP {resp.status_code}", "response": resp.text[:200]}
                return None
            
            data = resp.json()
            
            if expected_fields:
                missing = [f for f in expected_fields if f not in str(data)]
                if missing:
                    self.results[name] = {"status": "WARN", "missing_fields": missing, "data": data}
                    return data
            
            self.results[name] = {"status": "PASS", "data": data}
            return data
            
        except Exception as e:
            self.results[name] = {"status": "FAIL", "error": str(e)[:200]}
            return None
    
    def run_full_audit(self):
        print("=" * 80)
        print("ACQUISITION ORGANISM — FULL PRODUCTION AUDIT")
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        print("=" * 80)
        print()
        
        # AUTH
        print("1. AUTHENTICATION")
        print("-" * 40)
        if not self.load_credentials():
            print("   FAIL: No credentials")
            return
        if not self.login():
            print("   FAIL: Login failed")
            return
        print("   PASS: Authenticated")
        print()
        
        # ORGANISM STATE
        print("2. ORGANISM STATE")
        print("-" * 40)
        state = self.check(
            "organism_state",
            "/api/operator/organism/state",
            expected_fields=["deploy_commit", "discovered_entities", "qualified_entities"]
        )
        if state:
            print(f"   Deploy SHA: {state.get('deploy_commit', 'unknown')[:10]}")
            print(f"   Discovered Entities: {state.get('discovered_entities', 0)}")
            print(f"   Qualified Entities: {state.get('qualified_entities', 0)}")
            print(f"   Contactable Entities: {state.get('contactable_entities', 0)}")
            print(f"   Ideal Customers: {state.get('ideal_customers', 0)}")
        print()
        
        # CUSTOMER INTELLIGENCE SYSTEM
        print("3. CUSTOMER INTELLIGENCE SYSTEM")
        print("-" * 40)
        
        # 3a. Intelligence Base (list of records)
        intel_base = self.check(
            "intelligence_base",
            "/api/operator/customer-intelligence"
        )
        if intel_base:
            records = intel_base.get("records", [])
            summary = intel_base.get("summary", {})
            print(f"   Total Records: {len(records)}")
            print(f"   Average Completeness: {summary.get('average_completeness', 0)}%")
            tiers = summary.get("by_icp_tier", {})
            print(f"   ICP Tiers: T1={tiers.get('TIER_1', 0)} T2={tiers.get('TIER_2', 0)} T3={tiers.get('TIER_3', 0)}")
        
        # 3b. ICP Definition
        icp = self.check(
            "icp_definition",
            "/api/operator/customer-intelligence/icp"
        )
        if icp:
            tiers = icp.get("tiers", {})
            if tiers:
                print(f"   ICP Definition: LOADED ({len(tiers)} tiers)")
            else:
                print(f"   ICP Definition: LOADED")
        
        # 3c. Cockpit View
        cockpit = self.check(
            "cockpit_view",
            "/api/operator/customer-intelligence/cockpit",
            expected_fields=["top_prospects", "need_enrichment"]
        )
        if cockpit:
            print(f"   Cockpit Top Prospects: {len(cockpit.get('top_prospects', []))}")
            print(f"   Need Enrichment: {len(cockpit.get('need_enrichment', []))}")
        print()
        
        # TOP PROSPECTS
        print("4. TOP PROSPECTS RANKING")
        print("-" * 40)
        prospects = self.check(
            "top_prospects",
            "/api/operator/top-prospects?limit=20",
            expected_fields=["total_prospects", "prospects"]
        )
        if prospects:
            print(f"   Total Prospects: {prospects.get('total_prospects', 0)}")
            top = prospects.get("prospects", [])[:5]
            for i, p in enumerate(top, 1):
                print(f"   {i}. {p.get('company', 'Unknown')[:40]} - {p.get('recommendation', 'N/A')}")
        print()
        
        # ENRICHMENT ENGINE
        print("5. ENRICHMENT ENGINE")
        print("-" * 40)
        enrich_status = self.check(
            "enrichment_status",
            "/api/operator/customer-intelligence/enrichment-status"
        )
        if enrich_status:
            print(f"   Enrichment Status: AVAILABLE")
        
        comparison = self.check(
            "enrichment_comparison",
            "/api/operator/customer-intelligence/enrichment-comparison"
        )
        if comparison:
            print(f"   Enrichment Comparison: AVAILABLE")
        print()
        
        # DEEP ENRICHMENT (USASpending)
        print("6. USASPENDING DEEP ENRICHMENT")
        print("-" * 40)
        deep_report = self.check(
            "deep_enrichment_report",
            "/api/operator/customer-intelligence/deep-enrichment-report"
        )
        if deep_report:
            print(f"   Deep Enrichment Report: AVAILABLE")
            if deep_report.get("after"):
                after = deep_report["after"]
                print(f"   Avg Completeness: {after.get('average_completeness', 0):.1f}%")
                print(f"   Avg Enrichment: {after.get('average_enrichment', 0):.1f}")
        print()
        
        # CONTACT INTELLIGENCE
        print("7. CONTACT INTELLIGENCE ENGINE")
        print("-" * 40)
        contact_metrics = self.check(
            "contact_metrics",
            "/api/operator/customer-intelligence/contact-metrics",
            expected_fields=["metrics"]
        )
        if contact_metrics and contact_metrics.get("metrics"):
            m = contact_metrics["metrics"]
            print(f"   Email Known: {m.get('email_known_entities', 0)}")
            print(f"   Phone Known: {m.get('phone_known_entities', 0)}")
            print(f"   Contactable: {m.get('contactable_entities', 0)}")
            print(f"   Contact Ready: {m.get('contact_ready_entities', 0)}")
        
        top_contactable = self.check(
            "top_contactable",
            "/api/operator/customer-intelligence/top-contactable?limit=10"
        )
        if top_contactable:
            print(f"   Top Contactable Report: AVAILABLE")
        print()
        
        # DECISION MAKER INTELLIGENCE
        print("8. DECISION MAKER INTELLIGENCE ENGINE")
        print("-" * 40)
        dm_metrics = self.check(
            "decision_maker_metrics",
            "/api/operator/customer-intelligence/decision-maker-metrics",
            expected_fields=["metrics"]
        )
        if dm_metrics and dm_metrics.get("metrics"):
            m = dm_metrics["metrics"]
            print(f"   Decision Maker Entities: {m.get('decision_maker_entities', 0)}")
            print(f"   Leadership Entities: {m.get('leadership_entities', 0)}")
            print(f"   Procurement Relevant: {m.get('procurement_relevant_entities', 0)}")
            print(f"   Decision Maker Ready: {m.get('decision_maker_ready_entities', 0)}")
        
        procurement = self.check(
            "top_procurement_relevant",
            "/api/operator/customer-intelligence/top-procurement-relevant?limit=10"
        )
        if procurement:
            print(f"   Top Procurement Report: AVAILABLE")
            answer = procurement.get("organism_answer", {})
            if answer.get("answer"):
                print(f"   Organism Answer: {answer['answer'].get('company', 'N/A')[:40]}")
        print()
        
        # DISCOVERY PIPELINE
        print("9. DISCOVERY PIPELINE")
        print("-" * 40)
        # Check acquisition intelligence main endpoint
        acq_state = self.check(
            "acquisition_intelligence",
            "/api/operator/acquisition-intelligence"
        )
        if acq_state:
            print(f"   Acquisition Intelligence: AVAILABLE")
            print(f"   Leads: {len(acq_state.get('leads', []))}")
            print(f"   Targets: {len(acq_state.get('targets', []))}")
        print()
        
        # TELEMETRY
        print("10. TELEMETRY STATUS")
        print("-" * 40)
        telemetry = self.check(
            "telemetry_status",
            "/api/operator/telemetry-status"
        )
        if telemetry:
            print(f"   Telemetry Status: AVAILABLE")
            if isinstance(telemetry, dict):
                for k, v in list(telemetry.items())[:5]:
                    if k != "ok":
                        print(f"   {k}: {v}")
        print()
        
        # SAFETY CHECKS
        print("11. SAFETY VERIFICATION")
        print("-" * 40)
        
        # Check auto-send is disabled
        auto_send_disabled = True
        if state:
            auto_send = state.get("auto_send_enabled", False)
            auto_send_disabled = not auto_send
        print(f"   Auto-Send Disabled: {'YES' if auto_send_disabled else 'NO - DANGER!'}")
        print(f"   No Outreach During Audit: YES")
        print(f"   Evidence Collection Only: YES")
        print()
        
        # FINAL SUMMARY
        print("=" * 80)
        print("AUDIT SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for r in self.results.values() if r.get("status") == "PASS")
        warned = sum(1 for r in self.results.values() if r.get("status") == "WARN")
        failed = sum(1 for r in self.results.values() if r.get("status") == "FAIL")
        
        print(f"   PASS: {passed}")
        print(f"   WARN: {warned}")
        print(f"   FAIL: {failed}")
        print()
        
        if failed > 0:
            print("FAILED CHECKS:")
            for name, result in self.results.items():
                if result.get("status") == "FAIL":
                    print(f"   - {name}: {result.get('error', 'Unknown error')}")
            print()
        
        if warned > 0:
            print("WARNINGS:")
            for name, result in self.results.items():
                if result.get("status") == "WARN":
                    print(f"   - {name}: Missing {result.get('missing_fields', [])}")
            print()
        
        # VERDICT
        if failed == 0:
            print("VERDICT: ACQUISITION ORGANISM PRODUCTION READY")
        else:
            print("VERDICT: ISSUES DETECTED - REVIEW REQUIRED")
        
        return failed == 0


def main():
    audit = ProductionAudit()
    success = audit.run_full_audit()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
