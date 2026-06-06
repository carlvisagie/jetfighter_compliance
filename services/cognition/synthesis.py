from typing import Any, Dict, List
from datetime import datetime, timezone
from services.cognition.schemas import AwarenessState

def synthesize_awareness(
    profile: Dict[str, Any],
    classifications: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    gaps: List[Dict[str, Any]],
    review_queue: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]]
) -> AwarenessState:
    knows: List[str] = []
    does_not_know: List[str] = []
    contradictions: List[Dict[str, Any]] = []
    stale_info: List[Dict[str, Any]] = []
    
    # 1. Identify contradictions
    # From profile company name candidates
    conflicting_companies = [
        c for c in profile.get("company_name_candidates", [])
        if c.get("status") == "conflicting"
    ]
    if conflicting_companies:
        contradictions.append({
            "field": "company_name",
            "values": [c.get("value") for c in conflicting_companies]
        })
        
    # From review queue (kind == "conflicting_extraction")
    for item in review_queue:
        if item.get("kind") == "conflicting_extraction":
            contradictions.append({
                "field": item.get("field", "unknown"),
                "values": item.get("candidates", [])
            })

    # 2. Identify known facts
    # We consider entities with confidence > 0.55 as known
    total_confidence = 0.0
    known_entities_count = 0
    for ent in entities:
        if ent.get("confidence", 0) > 0.55:
            knows.append(f"{ent.get('type')}: {ent.get('value')}")
            total_confidence += ent.get("confidence", 0)
            known_entities_count += 1
            
    # Add domain knowledge
    domain = profile.get("primary_domain")
    if domain and domain != "general":
        knows.append(f"domain: {domain}")
        
    # Document inventory
    for doc in profile.get("document_inventory", []):
        knows.append(f"document: {doc.get('document_type')}")
        
    # 3. Identify unknown facts
    # Basic required facts we expect but might be missing
    basic_fields = ["company_name", "emails", "phones"]
    for field in basic_fields:
        if not profile.get(field) and not profile.get(f"{field}_candidates"):
            does_not_know.append(field)
            
    # 4. Identify stale info
    now = datetime.now(timezone.utc)
    for ent in entities:
        created_utc = ent.get("created_utc")
        if created_utc:
            try:
                dt = datetime.fromisoformat(created_utc.replace("Z", "+00:00"))
                age_days = (now - dt).days
                if age_days > 365:
                    stale_info.append({
                        "item": f"{ent.get('type')}: {ent.get('value')}",
                        "age_days": age_days
                    })
            except Exception:
                pass

    # 5. Compute confidence level
    # Simple average of high confidence entities + classifications
    clf_conf = sum(c.get("confidence", 0) for c in classifications)
    total_conf = total_confidence + clf_conf
    count = known_entities_count + len(classifications)
    confidence_level = total_conf / count if count > 0 else 0.0
    if confidence_level > 1.0:
        confidence_level = 1.0

    # Ensure blind organism state is explicitly represented
    has_files = len(profile.get("document_inventory", [])) > 0
    if has_files and confidence_level < 0.1:
        if not domain or domain == "general":
            does_not_know.append("domain_context")
        if not profile.get("company_name"):
            if "company_name" not in does_not_know:
                does_not_know.append("company_name")

    return AwarenessState(
        knows=knows,
        does_not_know=does_not_know,
        contradictions=contradictions,
        stale_info=stale_info,
        confidence_level=confidence_level
    )
