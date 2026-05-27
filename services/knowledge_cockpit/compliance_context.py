"""Compliance intelligence → knowledge cockpit context."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .encyclopedia import match_concepts_in_text, search_concepts
from .operational_explainer import explain_text


def build_compliance_context(
    *,
    summary: str = "",
    frameworks: Optional[List[str]] = None,
    change_id: str = "",
) -> Dict[str, Any]:
    fw = frameworks or []
    blob = f"{summary}\n" + " ".join(fw)
    explain = explain_text(blob)
    doc_recs: List[Dict[str, Any]] = []
    try:
        from services.compliance_intelligence.knowledge_bridge import recommend_knowledge_updates
        from services.compliance_intelligence.schemas import ChangeRecord, ClassificationResult

        cid = change_id or "CHG-CTX"
        change = ChangeRecord(
            change_id=cid,
            source_id="operator",
            change_type="changed_content",
            diff_summary=summary[:500],
        )
        clf = ClassificationResult(change_id=cid, frameworks=fw, summary=summary[:500])
        doc_recs = recommend_knowledge_updates(change, clf)
    except Exception:
        pass

    concepts = match_concepts_in_text(blob, limit=8) or search_concepts(" ".join(fw), limit=6)
    return {
        "ok": True,
        "what_changed": summary,
        "plain_english": _plain_meaning(summary, fw),
        "affected_concepts": [{"id": c.get("id"), "term": c.get("term")} for c in concepts],
        "why_operator_should_care": (
            "Authoritative sources shifted — verify SSP/POA&M and customer messaging before next award cycle."
            if fw
            else "Monitor for contract or assessment impact."
        ),
        "related_runbook_topics": doc_recs[:5],
        "explain": explain,
    }


def _plain_meaning(summary: str, frameworks: List[str]) -> str:
    if not summary:
        return "No change summary provided."
    if frameworks:
        return (
            f"Update touches {', '.join(frameworks)}. Review whether your SSP narratives and "
            f"customer-facing guidance still match the published requirement."
        )
    return summary[:400]
