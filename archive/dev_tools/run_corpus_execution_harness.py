import json
import logging
from datetime import datetime, timezone
from collections import Counter
from services.cognition.synthesis import synthesize_awareness
from services.cognition.reasoning import evaluate_all_gaps
from services.cognition.document_generation.engine import generate_documents_for_resolutions
from services.cognition.validation import build_validation_report
from services.cognition.metrics import compute_metrics
from services.cognition.scorecard import calculate_scorecard, evaluate_launch_gate

STANDARD_GAPS = [
    {"gap_id": "ssp_poam", "label": "SSP or POA&M"},
    {"gap_id": "access_control", "label": "Access Control"},
    {"gap_id": "incident_response", "label": "IR Plan"},
    {"gap_id": "vendor_policy", "label": "Vendor Policy"},
    {"gap_id": "backup_evidence", "label": "Backup"},
    {"gap_id": "training_record", "label": "Training"},
    {"gap_id": "mfa_evidence", "label": "MFA Screenshot"}
]

def make_entity(typ, val, conf=0.9, days_old=0):
    now = datetime.now(timezone.utc)
    ts = datetime.fromtimestamp(now.timestamp() - (days_old * 86400)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"type": typ, "value": val, "confidence": conf, "created_utc": ts}

CORPUS = [
    {
        "id": "1_conflicting_names",
        "desc": "Conflicting company names",
        "profile": {"company_name_candidates": [{"value": "Acme Corp", "status": "conflicting"}, {"value": "Acme LLC", "status": "conflicting"}], "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 3,
            "min_confidence": 0.8,
            "safety_warnings": ["Contradiction detected in company_name"]
        }
    },
    {
        "id": "2_conflicting_domains",
        "desc": "Conflicting domains",
        "profile": {"primary_domain": "cmmc", "document_inventory": [{"document_type": "policy"}]},
        "review_queue": [{"kind": "conflicting_extraction", "field": "domain", "candidates": ["cmmc", "hipaa"]}],
        "entities": [make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": ["domain: cmmc"],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence", "missing_company_name"],
            "min_reviews": 3,
            "min_confidence": 0.8,
            "safety_warnings": ["Contradiction detected in domain"]
        }
    },
    {
        "id": "3_multiple_subsidiaries",
        "desc": "Multiple subsidiaries",
        "profile": {"company_name": "Global Corp", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("company_name", "Sub A"), make_entity("company_name", "Sub B"), make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "vendor_policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    },
    {
        "id": "4_mixed_frameworks",
        "desc": "Mixed frameworks (HIPAA + CMMC)",
        "profile": {"primary_domain": "cmmc", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("domain", "hipaa"), make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": ["domain: hipaa", "domain: cmmc"],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence", "missing_company_name"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    },
    {
        "id": "5_missing_pages",
        "desc": "Missing pages",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "partial_policy"}]},
        "classifications": [{"document_type": "policy", "confidence": 0.3}],
        "entities": [make_entity("technology", "AWS", conf=0.4)],
        "ground_truth": {
            "frameworks": [],
            "generated": ["access_control_policy", "incident_response_plan", "policy", "training_policy"],
            "requested": ["ssp_poam", "backup_evidence", "mfa_evidence"],
            "min_reviews": 0,
            "min_confidence": 0.0,
            "safety_warnings": []
        }
    },
    {
        "id": "6_ocr_corruption",
        "desc": "OCR corruption",
        "profile": {"document_inventory": [{"document_type": "scan"}]},
        "entities": [make_entity("technology", "A#@!WS", conf=0.2), make_entity("company_name", "Ac^^e", conf=0.1)],
        "ground_truth": {
            "frameworks": [],
            "generated": ["access_control_policy", "incident_response_plan", "policy", "training_policy"],
            "requested": ["missing_company_name", "missing_domain", "ssp_poam", "backup_evidence", "mfa_evidence"],
            "min_reviews": 0,
            "min_confidence": 0.0,
            "safety_warnings": []
        }
    },
    {
        "id": "7_duplicate_uploads",
        "desc": "Duplicate uploads",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}, {"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS"), make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    },
    {
        "id": "8_stale_documents",
        "desc": "Stale documents",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS", days_old=400)],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": [] # stale info caught but no safety warning
        }
    },
    {
        "id": "9_contradictory_policies",
        "desc": "Contradictory policies",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "review_queue": [{"kind": "conflicting_extraction", "field": "mfa_enforced", "candidates": ["yes", "no"]}],
        "entities": [make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 3,
            "min_confidence": 0.8,
            "safety_warnings": ["Contradiction detected in mfa_enforced"]
        }
    },
    {
        "id": "10_missing_signatures",
        "desc": "Missing signatures",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    },
    {
        "id": "11_mixed_vendor",
        "desc": "Mixed vendor environments",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS"), make_entity("technology", "Azure"), make_entity("technology", "Okta"), make_entity("technology", "Entra ID")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    },
    {
        "id": "12_wrong_filenames",
        "desc": "Wrong file names",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "recipe.pdf"}]},
        "classifications": [{"document_type": "policy", "confidence": 0.9}],
        "entities": [make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    },
    {
        "id": "13_incomplete_asset_inventory",
        "desc": "Incomplete asset inventories",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "Laptop")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "training_policy"],
            "requested": ["backup_evidence", "mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    },
    {
        "id": "14_ambiguous_idp",
        "desc": "Ambiguous identity providers",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "SSO Login Page", conf=0.6)],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "training_policy"],
            "requested": ["backup_evidence", "mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.5,
            "safety_warnings": []
        }
    },
    {
        "id": "15_ambiguous_cloud",
        "desc": "Ambiguous cloud providers",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "Cloud Server", conf=0.6)],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "training_policy"],
            "requested": ["backup_evidence", "mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.5,
            "safety_warnings": []
        }
    },
    {
        "id": "16_no_contact_info",
        "desc": "No contact information",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    },
    {
        "id": "17_no_company_name",
        "desc": "No company name",
        "profile": {"document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["missing_company_name", "mfa_evidence"],
            "min_reviews": 1,
            "min_confidence": 0.0,
            "safety_warnings": []
        }
    },
    {
        "id": "18_excessive_irrelevant",
        "desc": "Excessive irrelevant documents",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "receipt"} for _ in range(50)]},
        "entities": [],
        "ground_truth": {
            "frameworks": [],
            "generated": ["access_control_policy", "incident_response_plan", "policy", "training_policy"],
            "requested": ["missing_domain", "ssp_poam", "backup_evidence", "mfa_evidence"],
            "min_reviews": 0,
            "min_confidence": 0.0,
            "safety_warnings": []
        }
    },
    {
        "id": "19_legacy_technologies",
        "desc": "Legacy technologies",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "Windows Server 2003")],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "training_policy"],
            "requested": ["backup_evidence", "mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    },
    {
        "id": "20_conflicting_evidence_over_time",
        "desc": "Conflicting evidence over time",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS", days_old=300), make_entity("technology", "Azure", days_old=10)],
        "ground_truth": {
            "frameworks": [],
            "generated": ["ssp", "access_control_policy", "incident_response_plan", "policy", "backup_policy", "training_policy"],
            "requested": ["mfa_evidence"],
            "min_reviews": 2,
            "min_confidence": 0.8,
            "safety_warnings": []
        }
    }
]

def run_harness():
    results = []
    
    for c in CORPUS:
        # 1. Ingest & 2. Run EI (Simulated by input structure)
        # 3. Run Cognition
        state = synthesize_awareness(
            profile=c.get("profile", {}),
            classifications=c.get("classifications", []),
            entities=c.get("entities", []),
            gaps=STANDARD_GAPS,
            review_queue=c.get("review_queue", []),
            timeline=[]
        )
        
        resolutions = evaluate_all_gaps(STANDARD_GAPS, state)
        docs = generate_documents_for_resolutions(resolutions, state)
        
        # 4. Run Validation
        validation = build_validation_report(c["id"], state, resolutions, docs)
        
        # 5. Run Metrics
        metrics = compute_metrics(state, resolutions)
        
        # 6. Compare vs Ground Truth
        gt = c["ground_truth"]
        
        actual_frameworks = [f for f in state.knows if f.startswith("domain: ")]
        actual_generated = [d.document_type for d in validation.documents_generated]
        actual_requested = [r.gap_id for r in validation.requests]
        actual_reviews = len(validation.human_review_items)
        actual_confidence = validation.confidence_summary
        actual_warnings = validation.safety_warnings
        
        framework_acc = 100.0 if set(actual_frameworks) == set(gt["frameworks"]) else 0.0
        
        gen_acc = 100.0 if set(actual_generated) == set(gt["generated"]) else 0.0
        req_acc = 100.0 if set(actual_requested) == set(gt["requested"]) else 0.0
        gap_acc = (gen_acc + req_acc) / 2.0
        
        review_acc = 100.0 if actual_reviews >= gt["min_reviews"] and set(actual_warnings) == set(gt["safety_warnings"]) else 0.0
        conf_acc = 100.0 if actual_confidence >= gt["min_confidence"] else 0.0
        
        # Determine root causes if any failed
        failures = []
        if framework_acc < 100: failures.append("Framework Extraction")
        if gen_acc < 100: failures.append("Generation Logic")
        if req_acc < 100: failures.append("Request Logic")
        if review_acc < 100: failures.append("Review Flagging")
        if conf_acc < 100: failures.append("Confidence Scoring")
        
        passed = len(failures) == 0
        
        failure_details = []
        if not passed:
            if framework_acc < 100:
                failure_details.append({
                    "category": "Framework Accuracy",
                    "expected": gt["frameworks"],
                    "actual": actual_frameworks,
                    "root_cause": "Failed to extract correct frameworks",
                    "recommended_fix": "Improve primary_domain and document context extraction"
                })
            if gen_acc < 100:
                failure_details.append({
                    "category": "Generation Accuracy",
                    "expected": gt["generated"],
                    "actual": actual_generated,
                    "root_cause": "Generation Logic",
                    "recommended_fix": "Update Empty State Tolerance threshold to strictly require company_name regardless of tech confidence." if c["id"] == "17_no_company_name" else "Review generation rules"
                })
            if req_acc < 100:
                failure_details.append({
                    "category": "Request Accuracy",
                    "expected": gt["requested"],
                    "actual": actual_requested,
                    "root_cause": "Request Logic",
                    "recommended_fix": "Update Empty State Tolerance threshold to strictly require company_name regardless of tech confidence." if c["id"] == "17_no_company_name" else "Review request logic"
                })
            if review_acc < 100:
                failure_details.append({
                    "category": "Review Accuracy",
                    "expected": f">= {gt['min_reviews']} reviews, warnings: {gt['safety_warnings']}",
                    "actual": f"{actual_reviews} reviews, warnings: {actual_warnings}",
                    "root_cause": "Review Flagging",
                    "recommended_fix": "Improve contradiction detection to force low confidence on critical entity conflicts."
                })
            if conf_acc < 100:
                failure_details.append({
                    "category": "Confidence Accuracy",
                    "expected": f">= {gt['min_confidence']}",
                    "actual": actual_confidence,
                    "root_cause": "Confidence Scoring",
                    "recommended_fix": "Adjust confidence weights for degraded inputs"
                })

        results.append({
            "id": c["id"],
            "desc": c["desc"],
            "framework_accuracy": framework_acc,
            "gap_accuracy": gap_acc,
            "generation_accuracy": gen_acc,
            "request_accuracy": req_acc,
            "review_accuracy": review_acc,
            "confidence_accuracy": conf_acc,
            "workload_elimination": metrics.workload_elimination_percentage,
            "passed": passed,
            "failure_details": failure_details,
            "root_cause": failure_details[0]["root_cause"] if failure_details else None
        })
        
    with open("corpus_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count
    
    all_failures = []
    for r in results:
        for f in r.get("failure_details", []):
            all_failures.append(f)
    
    top_categories = [k for k, v in Counter(f["category"] for f in all_failures).most_common(3)]
    
    most_common_rc = [k for k, v in Counter(f["root_cause"] for f in all_failures).most_common(3)]
    
    recommended_fixes = list(set(f["recommended_fix"] for f in all_failures))
        
    overall = {
        "pass_rate": (passed_count / total) * 100.0,
        "failure_rate": (failed_count / total) * 100.0,
        "total_scenarios": total,
        "top_failure_categories": top_categories,
        "most_common_root_causes": most_common_rc,
        "recommended_fixes": recommended_fixes,
        "failures": all_failures
    }
    
    with open("overall_corpus_score.json", "w") as f:
        json.dump(overall, f, indent=2)
        
    print(f"Corpus harness finished. Pass rate: {overall['pass_rate']}%")

if __name__ == "__main__":
    run_harness()
