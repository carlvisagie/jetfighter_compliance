"""Map acquisition prey / Reddit burden to knowledge concepts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .encyclopedia import match_concepts_in_text, search_concepts
from .operational_explainer import explain_text


def build_acquisition_context(
    *,
    title: str = "",
    body: str = "",
    discovery_cluster: str = "",
    burden_category: str = "",
    prey_reasons: Optional[List[str]] = None,
) -> Dict[str, Any]:
    blob = f"{title}\n{body}\n{discovery_cluster}\n{burden_category}\n" + " ".join(prey_reasons or [])
    explain = explain_text(blob)
    cluster_map = {
        "vendor_pressure": ["vendor-questionnaire", "prime-contractor", "evidence"],
        "direct_cmmc": ["cmmc", "cmmc-level-2", "sprs-score"],
        "documentation_burden": ["ssp", "poam", "evidence"],
        "cybersecurity_questionnaire": ["security-questionnaire", "vendor-questionnaire"],
        "mfa_security_requirements": ["mfa", "access-control"],
        "government_contract": ["dfars-7012", "cui", "flowdown"],
        "subcontractor_compliance": ["subcontractor", "flowdown", "cmmc"],
    }
    extra_ids = cluster_map.get((discovery_cluster or "").strip(), [])
    concepts = list(explain.get("matched_concepts") or [])
    for cid in extra_ids:
        from .encyclopedia import get_concept

        c = get_concept(cid)
        if c and not any(x.get("id") == cid for x in concepts):
            concepts.append({"id": c["id"], "term": c.get("term")})

    prospect_meaning = _prospect_interpretation(title, body, discovery_cluster)
    likely_paperwork = _paperwork_hints(blob, prey_reasons or [])

    return {
        "ok": True,
        "prospect_likely_means": prospect_meaning,
        "frameworks_may_apply": _frameworks(concepts),
        "likely_paperwork": likely_paperwork,
        "burden_expressed": burden_category or discovery_cluster or "operational_security",
        "related_concepts": concepts[:10],
        "explain": explain,
        "suggested_actions": [
            "Confirm whether they handle FCI only or CUI (drives L1 vs L2).",
            "Ask what document the customer sent (questionnaire, flowdown, SSP request).",
            "Route to upload-first: accept messy partial paperwork before prescribing framework.",
        ],
    }


def _prospect_interpretation(title: str, body: str, cluster: str) -> str:
    blob = f"{title} {body}".lower()
    if "which cmmc level" in blob or "what level" in blob and "cmmc" in blob:
        return (
            "They likely received a flowdown or customer questionnaire and do not yet know "
            "whether FCI (Level 1) or CUI (Level 2 / 800-171) applies."
        )
    if "questionnaire" in blob or cluster == "vendor_pressure":
        return "A third party is auditing their security posture — deadline-driven paperwork burden."
    if "mfa" in blob:
        return "Customer mandates stronger identity controls — often first concrete technical ask."
    if "policy" in blob or "document" in blob:
        return "They need written proof of controls (policies/procedures) not just verbal assurances."
    return "Operational security/compliance pressure without clear framework vocabulary yet."


def _frameworks(concepts: List[Dict[str, Any]]) -> List[str]:
    fw = []
    ids = {c.get("id") for c in concepts}
    if ids & {"cmmc", "cmmc-level-2", "nist-800-171", "sprs-score"}:
        fw.append("CMMC / NIST 800-171")
    if "dfars-7012" in ids or "flowdown" in ids:
        fw.append("DFARS 7012 flowdown")
    if "vendor-questionnaire" in ids:
        fw.append("Customer/vendor security assessment")
    return fw or ["Undetermined — confirm FCI vs CUI first"]


def _paperwork_hints(blob: str, prey_reasons: List[str]) -> List[str]:
    hints = []
    bl = blob.lower()
    if "questionnaire" in bl:
        hints.append("Security questionnaire (SIG/custom)")
    if "policy" in bl:
        hints.append("Policies / procedures")
    if "mfa" in bl:
        hints.append("MFA proof screenshots")
    if "ssp" in bl or "system security" in bl:
        hints.append("SSP or security plan excerpt")
    for r in prey_reasons:
        if "paperwork" in r.lower() or "documentation" in r.lower():
            hints.append(r)
    return hints[:6] or ["Unknown packet — ask what file/email they received"]
