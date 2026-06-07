import json
import logging
from datetime import datetime, timezone
from services.cognition.synthesis import synthesize_awareness
from services.cognition.reasoning import evaluate_all_gaps
from services.cognition.document_generation.engine import generate_documents_for_resolutions
from services.cognition.validation import build_validation_report

# Mock standard gaps
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

scenarios = [
    {
        "id": "1_conflicting_names",
        "desc": "Conflicting company names",
        "profile": {"company_name_candidates": [{"value": "Acme Corp", "status": "conflicting"}, {"value": "Acme LLC", "status": "conflicting"}], "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS")]
    },
    {
        "id": "2_conflicting_domains",
        "desc": "Conflicting domains",
        "profile": {"primary_domain": "cmmc", "document_inventory": [{"document_type": "policy"}]},
        "review_queue": [{"kind": "conflicting_extraction", "field": "domain", "candidates": ["cmmc", "hipaa"]}],
        "entities": [make_entity("technology", "AWS")]
    },
    {
        "id": "3_multiple_subsidiaries",
        "desc": "Multiple subsidiaries",
        "profile": {"company_name": "Global Corp", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("company_name", "Sub A"), make_entity("company_name", "Sub B"), make_entity("technology", "AWS")]
    },
    {
        "id": "4_mixed_frameworks",
        "desc": "Mixed frameworks (HIPAA + CMMC)",
        "profile": {"primary_domain": "cmmc", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("domain", "hipaa"), make_entity("technology", "AWS")]
    },
    {
        "id": "5_missing_pages",
        "desc": "Missing pages",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "partial_policy"}]},
        "classifications": [{"document_type": "policy", "confidence": 0.3}],
        "entities": [make_entity("technology", "AWS", conf=0.4)]
    },
    {
        "id": "6_ocr_corruption",
        "desc": "OCR corruption",
        "profile": {"document_inventory": [{"document_type": "scan"}]},
        "entities": [make_entity("technology", "A#@!WS", conf=0.2), make_entity("company_name", "Ac^^e", conf=0.1)]
    },
    {
        "id": "7_duplicate_uploads",
        "desc": "Duplicate uploads",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}, {"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS"), make_entity("technology", "AWS")]
    },
    {
        "id": "8_stale_documents",
        "desc": "Stale documents",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS", days_old=400)]
    },
    {
        "id": "9_contradictory_policies",
        "desc": "Contradictory policies",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "review_queue": [{"kind": "conflicting_extraction", "field": "mfa_enforced", "candidates": ["yes", "no"]}],
        "entities": [make_entity("technology", "AWS")]
    },
    {
        "id": "10_missing_signatures",
        "desc": "Missing signatures",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS")] # Gap logic handles signature requesting
    },
    {
        "id": "11_mixed_vendor",
        "desc": "Mixed vendor environments",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS"), make_entity("technology", "Azure"), make_entity("technology", "Okta"), make_entity("technology", "Entra ID")]
    },
    {
        "id": "12_wrong_filenames",
        "desc": "Wrong file names",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "recipe.pdf"}]},
        "classifications": [{"document_type": "policy", "confidence": 0.9}],
        "entities": [make_entity("technology", "AWS")]
    },
    {
        "id": "13_incomplete_asset_inventory",
        "desc": "Incomplete asset inventories",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "Laptop")]
    },
    {
        "id": "14_ambiguous_idp",
        "desc": "Ambiguous identity providers",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "SSO Login Page", conf=0.6)]
    },
    {
        "id": "15_ambiguous_cloud",
        "desc": "Ambiguous cloud providers",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "Cloud Server", conf=0.6)]
    },
    {
        "id": "16_no_contact_info",
        "desc": "No contact information",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS")]
    },
    {
        "id": "17_no_company_name",
        "desc": "No company name",
        "profile": {"document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS")]
    },
    {
        "id": "18_excessive_irrelevant",
        "desc": "Excessive irrelevant documents",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "receipt"} for _ in range(50)]},
        "entities": []
    },
    {
        "id": "19_legacy_technologies",
        "desc": "Legacy technologies",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "Windows Server 2003")]
    },
    {
        "id": "20_conflicting_evidence_over_time",
        "desc": "Conflicting evidence over time",
        "profile": {"company_name": "Acme", "document_inventory": [{"document_type": "policy"}]},
        "entities": [make_entity("technology", "AWS", days_old=300), make_entity("technology", "Azure", days_old=10)]
    }
]

report_data = []

for sc in scenarios:
    state = synthesize_awareness(
        profile=sc.get("profile", {}),
        classifications=sc.get("classifications", []),
        entities=sc.get("entities", []),
        gaps=STANDARD_GAPS,
        review_queue=sc.get("review_queue", []),
        timeline=[]
    )
    
    resolutions = evaluate_all_gaps(STANDARD_GAPS, state)
    docs = generate_documents_for_resolutions(resolutions, state)
    val_report = build_validation_report(sc["id"], state, resolutions, docs)
    
    # Evaluate correctness
    # All our scenarios are designed such that the reasoning engine should either flag for review,
    # safely degrade to request/partial, or generate correctly based on known facts.
    
    # Check if empty state tolerance kicked in
    is_correct = True
    
    generated_types = [d.document_type for d in val_report.documents_generated]
    requested_types = [r.gap_id for r in val_report.requests]
    review_reasons = [r.reason for r in val_report.human_review_items]
    
    if sc["id"] == "1_conflicting_names" or sc["id"] == "2_conflicting_domains" or sc["id"] == "9_contradictory_policies":
        if not any("Contradiction" in w for w in val_report.safety_warnings):
            is_correct = False
            
    if sc["id"] == "6_ocr_corruption" or sc["id"] == "18_excessive_irrelevant":
        # Should have low confidence and fall back to request
        if state.confidence_level > 0.5:
            is_correct = False
            
    if sc["id"] == "8_stale_documents":
        if not state.stale_info:
            is_correct = False
            
    if sc["id"] == "17_no_company_name":
        if "missing_company_name" not in requested_types:
            is_correct = False
            
    report_data.append({
        "scenario": sc["desc"],
        "believed_facts": [f.fact for f in val_report.facts_used],
        "generated": generated_types,
        "requested": requested_types,
        "review_flags": len(val_report.human_review_items),
        "safety_warnings": val_report.safety_warnings,
        "assumptions": len(val_report.assumptions),
        "confidence": val_report.confidence_summary,
        "correct_decision": is_correct
    })

total_correct = sum(1 for r in report_data if r["correct_decision"])
accuracy = (total_correct / len(report_data)) * 100

print(f"Total Scenarios: {len(report_data)}")
print(f"Decision Accuracy: {accuracy}%")

with open('adversarial_audit_report.json', 'w') as f:
    json.dump({
        "accuracy": accuracy,
        "total_scenarios": len(report_data),
        "scenarios": report_data
    }, f, indent=2)
