"""Central KYC memory API — read before action, write after action."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import DATA, PROJECTS
from .entity_graph import (
    add_ref,
    find_entity_id,
    get_entity,
    load_entities,
    upsert_entity,
)
from .learning import record_learning_signal
from .signals import append_signal, load_signals
from .timeline import append_timeline, load_timeline

logger = logging.getLogger(__name__)


def resolve_or_create_entity(
    *,
    email: str = "",
    company: str = "",
    contact_name: str = "",
    display_name: str = "",
    base: Optional[Path] = None,
) -> str:
    eid, _ = upsert_entity(
        email=email,
        company=company,
        contact_name=contact_name,
        display_name=display_name or company,
        base=base,
    )
    return eid


def read_entity_context(
    *,
    entity_id: str = "",
    email: str = "",
    company: str = "",
    lead_id: str = "",
    project_id: str = "",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Read canonical memory before scoring, kickoff, or ops action."""
    eid = entity_id or find_entity_id(
        email=email, company=company, lead_id=lead_id, project_id=project_id, base=base
    )
    if not eid:
        return {"entity_id": None, "known": False, "signals": [], "timeline": [], "entity": None}

    return {
        "entity_id": eid,
        "known": True,
        "entity": get_entity(eid, base),
        "signals": load_signals(eid, base)[-30:],
        "timeline": load_timeline(eid, base)[-40:],
        "prior_projects": [
            r.get("ref_id")
            for r in (get_entity(eid, base) or {}).get("refs", [])
            if r.get("ref_type") == "project"
        ],
        "prior_leads": [
            r.get("ref_id")
            for r in (get_entity(eid, base) or {}).get("refs", [])
            if r.get("ref_type") == "lead"
        ],
    }


def link_lead(lead_id: str, entity_id: str, payload: Optional[Dict[str, Any]] = None, base: Optional[Path] = None) -> None:
    add_ref(entity_id, "lead", lead_id, base)
    append_timeline(entity_id, "lead_linked", "lead", lead_id, payload, base)
    append_signal(entity_id, "acquisition", payload.get("source", "lead") if payload else "lead", 1.0, payload, base)


def link_inquiry(
    project_id: str,
    order_id: str,
    entity_id: str,
    payload: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> None:
    add_ref(entity_id, "project", project_id, base)
    add_ref(entity_id, "inquiry", order_id, base)
    append_timeline(entity_id, "inquiry_submitted", "project", project_id, payload, base)
    record_learning_signal("inquiry_submitted", "inquiry_to_intake", success=True, base=base)


def link_project(project_id: str, entity_id: str, meta: Optional[Dict[str, Any]] = None, base: Optional[Path] = None) -> None:
    add_ref(entity_id, "project", project_id, base)
    append_timeline(entity_id, "project_created", "project", project_id, meta, base)


def link_intake(project_id: str, entity_id: str, intake: Dict[str, Any], base: Optional[Path] = None) -> None:
    append_timeline(entity_id, "intake_completed", "project", project_id, {"company": intake.get("company")}, base)
    record_learning_signal(
        "intake_completed",
        "inquiry_to_intake",
        success=True,
        paperwork_hint=intake.get("notes", "")[:80],
        base=base,
    )
    flags = intake.get("external_flags") or {}
    if sum(1 for v in flags.values() if v) >= 3:
        append_signal(entity_id, "operational_complexity", "intake", 0.8, {"flags": flags}, base)


def link_artifact(
    project_id: str,
    filename: str,
    entity_id: str,
    fingerprint: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> None:
    append_timeline(entity_id, "evidence_uploaded", "project", project_id, {"filename": filename}, base)
    if fingerprint:
        append_signal(entity_id, "paperwork", "evidence", 0.5, fingerprint, base)
        cats = ",".join(fingerprint.get("categories") or [])
        if cats:
            record_learning_signal(f"doc:{cats}", "intake_to_evidence", success=True, paperwork_hint=cats, base=base)


def link_event(event_id: str, entity_id: str, project_id: str = "", payload: Optional[Dict[str, Any]] = None, base: Optional[Path] = None) -> None:
    append_timeline(entity_id, "ledger_event", "event", event_id, {"project_id": project_id, **(payload or {})}, base)


def link_outcome(
    entity_id: str,
    stage: str,
    success: bool,
    lead_id: str = "",
    project_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> None:
    append_timeline(entity_id, "outcome", "stage", stage, {"success": success, "lead_id": lead_id, "project_id": project_id}, base)
    if not success:
        record_learning_signal(stage, "lead_failed", success=False, base=base)


def reconstruct_journey(
    *,
    entity_id: str = "",
    project_id: str = "",
    lead_id: str = "",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    eid = entity_id or find_entity_id(lead_id=lead_id, project_id=project_id, base=base)
    if not eid and project_id:
        eid = find_entity_id(project_id=project_id, base=base)
    ctx = read_entity_context(entity_id=eid or "", base=base) if eid else {"known": False}

    journey = {
        "entity_id": eid,
        "context": ctx,
        "lead_id": lead_id,
        "project_id": project_id,
        "stages": [],
    }

    for step in ctx.get("timeline") or []:
        journey["stages"].append(
            {
                "when": step.get("when_utc"),
                "type": step.get("event_type"),
                "ref": f"{step.get('ref_type')}:{step.get('ref_id')}",
            }
        )

    if project_id:
        meta_path = PROJECTS / project_id / "meta.json"
        if meta_path.exists():
            journey["project_meta"] = json.loads(meta_path.read_text(encoding="utf-8"))
        intake_path = PROJECTS / project_id / "communications" / "intake.json"
        if intake_path.exists():
            journey["intake"] = json.loads(intake_path.read_text(encoding="utf-8"))

    try:
        from services.acquisition.forensics import reconstruct_journey as forensic_rebuild

        if project_id:
            journey["forensic"] = forensic_rebuild(project_id)
    except Exception as e:
        journey["forensic_error"] = str(e)

    return journey


# --- Safe wrappers for vessels (never break production) ---


def safe_read_before_lead_score(company: str, email: str, base: Optional[Path] = None) -> Dict[str, Any]:
    try:
        return read_entity_context(email=email, company=company, base=base)
    except Exception as e:
        logger.warning("Central memory read (lead score): %s", e)
        return {"known": False}


def safe_read_before_kickoff(email: str, name: str, company: str = "", base: Optional[Path] = None) -> Dict[str, Any]:
    try:
        return read_entity_context(email=email, company=company or name, base=base)
    except Exception as e:
        logger.warning("Central memory read (kickoff): %s", e)
        return {"known": False}


def safe_link_after_kickoff(
    project_id: str,
    order_id: str,
    email: str,
    name: str,
    skus: List[str],
    lead_id: str = "",
    base: Optional[Path] = None,
) -> Optional[str]:
    try:
        eid = resolve_or_create_entity(email=email, company=name, contact_name=name, base=base)
        link_project(project_id, eid, {"order_id": order_id, "skus": skus}, base)
        link_inquiry(project_id, order_id, eid, {"email": email, "name": name}, base)
        if lead_id:
            link_lead(lead_id, eid, {"source": "inquiry_ref"}, base)
        return eid
    except Exception as e:
        logger.warning("Central memory write (kickoff): %s", e)
        return None


def safe_write_after_inquiry(
    project_id: str,
    order_id: str,
    email: str,
    name: str,
    subject: str,
    message: str,
    lead_id: str = "",
    base: Optional[Path] = None,
) -> None:
    try:
        from services.acquisition.fingerprints import extract_ref_from_message

        lead_id = lead_id or extract_ref_from_message(message)
        eid = resolve_or_create_entity(email=email, contact_name=name, base=base)
        link_inquiry(project_id, order_id, eid, {"subject": subject, "message": message[:500]}, base)
        if lead_id:
            link_lead(lead_id, eid, {}, base)
            record_learning_signal(f"lead:{lead_id}", "lead_to_inquiry", success=True, base=base)
    except Exception as e:
        logger.warning("Central memory write (inquiry): %s", e)


def safe_write_after_intake(project_id: str, email: str, intake: Dict[str, Any], base: Optional[Path] = None) -> None:
    try:
        eid = resolve_or_create_entity(
            email=email,
            company=intake.get("company", ""),
            base=base,
        ) or find_entity_id(project_id=project_id, base=base)
        if eid:
            link_intake(project_id, eid, intake, base)
    except Exception as e:
        logger.warning("Central memory write (intake): %s", e)


def safe_write_after_evidence(project_id: str, filename: str, base: Optional[Path] = None) -> None:
    try:
        eid = find_entity_id(project_id=project_id, base=base)
        if not eid:
            return
        fp = None
        try:
            from services.acquisition.fingerprints import fingerprint_filename

            fp = fingerprint_filename(filename)
        except Exception:
            pass
        link_artifact(project_id, filename, eid, fp, base)
    except Exception as e:
        logger.warning("Central memory write (evidence): %s", e)


def lookup(
    *,
    entity_id: str = "",
    email: str = "",
    project_id: str = "",
    lead_id: str = "",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    from .learning import get_learning_summary
    from .self_healing import load_corrections, run_self_healing_scan

    journey = reconstruct_journey(entity_id=entity_id, project_id=project_id, lead_id=lead_id, base=base)
    heal = run_self_healing_scan(base=base, write_suggestions=False)
    return {
        "journey": journey,
        "learning": get_learning_summary(base),
        "self_healing": heal,
        "recent_corrections": load_corrections(base, 15),
    }
