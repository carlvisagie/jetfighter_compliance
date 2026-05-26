"""Forensic acquisition intelligence — organizational memory from onboarding artifacts."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import DATA, PROJECTS
from .fingerprints import (
    build_profiles,
    extract_ref_from_message,
    fingerprint_inquiry,
    fingerprint_intake,
    scan_evidence_dir,
)
from .history import (
    append_forensic_event,
    get_org_history,
    get_org_profile,
    list_forensic_events,
    resolve_org_key,
    upsert_org_profile,
)
from .memory import correlate_lead_to_project, record_outcome, recompute_weights_from_outcomes

logger = logging.getLogger(__name__)


def record_inquiry_submitted(
    project_id: str,
    email: str,
    name: str,
    subject: str,
    message: str,
    intel_base: Optional[Path] = None,
) -> Dict[str, Any]:
    payload = {"name": name, "email": email, "subject": subject, "message": message}
    inquiry_fp = fingerprint_inquiry(payload)
    org_key = resolve_org_key(email=email)
    lead_id = inquiry_fp.get("lead_ref") or ""
    append_forensic_event("inquiry_submitted", project_id, org_key, {"inquiry": inquiry_fp}, intel_base)
    profiles = build_profiles(inquiry_fp=inquiry_fp)
    upsert_org_profile(
        org_key,
        {
            "last_project_id": project_id,
            "last_lead_id": lead_id,
            "inquiry_fingerprint": inquiry_fp,
            **profiles,
        },
        intel_base,
    )
    record_outcome(
        lead_id=lead_id,
        project_id=project_id,
        org_key=org_key,
        stage="inquiry_submitted",
        success=True,
        metadata={"segment_subject": subject, "urgency_indicators": inquiry_fp.get("urgency_indicators")},
        base=intel_base,
    )
    if lead_id:
        correlate_lead_to_project(lead_id, project_id, intel_base)
    try:
        from services.acquisition.orchestration import track_funnel_event

        track_funnel_event(
            "inquiry_submitted",
            success=True,
            lead_id=lead_id,
            project_id=project_id,
            org_key=org_key,
            metadata={"subject": subject},
            base=intel_base,
        )
    except Exception:
        pass
    return {"org_key": org_key, "lead_id": lead_id, "profiles": profiles}


def record_intake_completed(
    project_id: str,
    email: str,
    intake: Dict[str, Any],
    intel_base: Optional[Path] = None,
) -> Dict[str, Any]:
    intake_fp = fingerprint_intake(intake)
    evidence_fp = scan_evidence_dir(project_id, PROJECTS)
    org_key = resolve_org_key(email=email, company=intake.get("company", ""))
    profile = get_org_profile(org_key, intel_base) or {}
    inquiry_fp = profile.get("inquiry_fingerprint") or {}
    profiles = build_profiles(intake_fp=intake_fp, evidence_fp=evidence_fp, inquiry_fp=inquiry_fp)
    append_forensic_event(
        "intake_completed",
        project_id,
        org_key,
        {"intake": intake_fp, "evidence": evidence_fp, "profiles": profiles},
        intel_base,
    )
    upsert_org_profile(
        org_key,
        {
            "last_project_id": project_id,
            "intake_fingerprint": intake_fp,
            "evidence_fingerprint": evidence_fp,
            **profiles,
        },
        intel_base,
    )
    lead_id = inquiry_fp.get("lead_ref") or profile.get("last_lead_id") or ""
    record_outcome(
        lead_id=lead_id,
        project_id=project_id,
        org_key=org_key,
        stage="intake_completed",
        success=True,
        metadata={
            "documentation_score": profiles["documentation_maturity_profile"]["score"],
            "compliance_score": profiles["compliance_readiness_profile"]["score"],
        },
        base=intel_base,
    )
    recompute_weights_from_outcomes(intel_base)
    try:
        from services.memory import safe_write_after_intake

        safe_write_after_intake(project_id, email, intake)
    except Exception:
        pass
    return {"org_key": org_key, "profiles": profiles}


def record_evidence_uploaded(
    project_id: str,
    filename: str,
    media_type: str,
    intel_base: Optional[Path] = None,
) -> None:
    from .fingerprints import fingerprint_filename

    fp = fingerprint_filename(filename)
    org_key = ""
    meta_path = PROJECTS / project_id / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        org_key = resolve_org_key(email=meta.get("customer", {}).get("email", ""))
    append_forensic_event(
        "evidence_uploaded",
        project_id,
        org_key,
        {"file": fp, "media_type": media_type},
        intel_base,
    )
    try:
        from services.memory import safe_write_after_evidence

        safe_write_after_evidence(project_id, filename)
    except Exception:
        pass


def reconstruct_journey(project_id: str, intel_base: Optional[Path] = None) -> Dict[str, Any]:
    events = list_forensic_events(project_id, intel_base)
    meta = {}
    mp = PROJECTS / project_id / "meta.json"
    if mp.exists():
        meta = json.loads(mp.read_text(encoding="utf-8"))
    intake = {}
    ip = PROJECTS / project_id / "communications" / "intake.json"
    if ip.exists():
        intake = json.loads(ip.read_text(encoding="utf-8"))
    email = meta.get("customer", {}).get("email", "")
    org_key = resolve_org_key(email=email, company=intake.get("company", ""))
    history = get_org_history(org_key, intel_base)
    profile = get_org_profile(org_key, intel_base)
    return {
        "project_id": project_id,
        "org_key": org_key,
        "customer": meta.get("customer"),
        "forensic_events": events,
        "org_history": history,
        "org_profile": profile,
        "intake": intake,
        "evidence_scan": scan_evidence_dir(project_id, PROJECTS),
    }


def org_intelligence_summary(org_key: str, intel_base: Optional[Path] = None) -> Dict[str, Any]:
    profile = get_org_profile(org_key, intel_base) or {}
    history = get_org_history(org_key, intel_base)
    return {
        "org_key": org_key,
        "profile": profile,
        "touch_count": len(history),
        "organizational_maturity_profile": profile.get("organizational_maturity_profile"),
        "documentation_maturity_profile": profile.get("documentation_maturity_profile"),
        "compliance_readiness_profile": profile.get("compliance_readiness_profile"),
    }


def safe_record_inquiry(
    project_id: str, email: str, name: str, subject: str, message: str, order_id: str = ""
) -> None:
    try:
        record_inquiry_submitted(project_id, email, name, subject, message)
    except Exception as e:
        logger.warning("Forensic inquiry record failed: %s", e)
    try:
        from services.acquisition.fingerprints import extract_ref_from_message
        from services.memory import safe_write_after_inquiry

        lead_id = extract_ref_from_message(message)
        oid = order_id or (project_id[2:].split("-")[0] if project_id.startswith("P-") else project_id)
        safe_write_after_inquiry(project_id, oid, email, name, subject, message, lead_id)
    except Exception as e:
        logger.warning("Central memory inquiry link failed: %s", e)


def safe_record_intake(project_id: str, email: str, intake: Dict[str, Any]) -> None:
    try:
        record_intake_completed(project_id, email, intake)
    except Exception as e:
        logger.warning("Forensic intake record failed: %s", e)


def safe_record_evidence(project_id: str, filename: str, media_type: str) -> None:
    try:
        record_evidence_uploaded(project_id, filename, media_type)
    except Exception as e:
        logger.warning("Forensic evidence record failed: %s", e)
