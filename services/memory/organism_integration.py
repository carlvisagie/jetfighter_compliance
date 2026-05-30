"""KYC organism integration registry — audit status and safe vessel adapters."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .central_memory import (
    _attach_entity_refs,
    _timeline_has,
    find_entity_id,
    link_event,
    link_outcome,
    link_project,
    read_entity_context,
    resolve_or_create_entity,
    safe_link_ledger_event,
)
from .entity_graph import get_entity
from .learning import record_learning_signal
from .timeline import append_timeline

logger = logging.getLogger(__name__)

# Registry: engine_id -> audit metadata (updated by run_integration_audit)
ENGINE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "central_memory": {
        "label": "Central memory (brain)",
        "paths": ["services/memory/"],
        "classification": "plugged",
        "reads": ["entities.jsonl", "timelines.jsonl", "signals.jsonl", "learning_state.json"],
        "writes": ["entities.jsonl", "timelines.jsonl", "signals.jsonl", "learning_state.json", "corrections.jsonl"],
        "read_before": True,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "none",
    },
    "acquisition_discovery": {
        "label": "Acquisition discovery / import",
        "paths": ["services/acquisition/discovery.py", "scripts/acquisition_import_candidates.py"],
        "classification": "plugged",
        "reads": ["data/memory/entities.jsonl (via safe_read_before_lead_score)"],
        "writes": ["data/memory/ (link_lead)", "data/acquisition/leads/"],
        "read_before": True,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
    },
    "acquisition_scoring": {
        "label": "Acquisition scoring / ranking",
        "paths": ["services/acquisition/scoring.py"],
        "classification": "plugged",
        "reads": ["memory_context from discovery"],
        "writes": ["data/acquisition/queue/ + telemetry lead_scored signals"],
        "read_before": True,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
        "fix_needed": "",
    },
    "acquisition_forensics": {
        "label": "Forensics / fingerprints",
        "paths": ["services/acquisition/forensics.py", "fingerprints.py", "history.py"],
        "classification": "plugged",
        "reads": ["project dirs", "data/acquisition/intelligence/"],
        "writes": ["forensic_events.jsonl", "org_profiles.jsonl", "central memory via bridge"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "medium",
        "duplicate_truth_risk": "medium",
        "fix_needed": "Forensic store parallels central; bridged on inquiry/intake/evidence",
    },
    "acquisition_memory_island": {
        "label": "Acquisition outcome memory (weights)",
        "paths": ["services/acquisition/memory.py"],
        "classification": "plugged",
        "reads": ["outcomes.jsonl"],
        "writes": ["outcomes.jsonl", "weights.json"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "medium",
        "duplicate_truth_risk": "medium",
        "fix_needed": "Parallel weights store; outcomes bridged to central timeline",
    },
    "inquiry_submit": {
        "label": "Inquiry submit",
        "paths": ["server.py (/api/inquiry/submit)", "ui/inquiry.html"],
        "classification": "plugged",
        "reads": ["optional ref in message"],
        "writes": ["data/inquiries/", "projects/", "central memory", "forensics"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
    },
    "intake": {
        "label": "Intake resolve / submit",
        "paths": ["server.py (/api/intake/*)", "ui/intake.html"],
        "classification": "plugged",
        "reads": ["intake token"],
        "writes": ["communications/intake.json", "process workflow", "central memory"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
    },
    "kickoff": {
        "label": "Kickoff / project creation",
        "paths": ["server.py (kickoff)", "services/projects.py"],
        "classification": "plugged",
        "reads": ["safe_read_before_kickoff"],
        "writes": ["projects/meta.json", "ledger", "central memory project_created"],
        "read_before": True,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
    },
    "workflow": {
        "label": "Workflow / process engine",
        "paths": ["services/process.py", "server.py (mark_done/set_phase)"],
        "classification": "plugged",
        "reads": ["data/process/{project}.json"],
        "writes": ["data/process/{project}.json"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "medium",
        "duplicate_truth_risk": "medium",
        "fix_needed": "",
    },
    "compliance_intelligence": {
        "label": "Continuous compliance intelligence",
        "paths": ["services/compliance_intelligence/", "services/engine.py (scheduler)"],
        "classification": "plugged",
        "reads": ["data/compliance_intelligence/sources.json", "public authority URLs"],
        "writes": ["snapshots/", "changes.jsonl", "central memory timeline", "telemetry"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
        "fix_needed": "Local snapshots are artifacts; timeline + review queue drive actions",
    },
    "evidence_intelligence": {
        "label": "Evidence intelligence (upload analysis)",
        "paths": ["services/evidence_intelligence/", "server.py (/api/evidence/register)"],
        "classification": "plugged",
        "reads": ["project evidence files"],
        "writes": ["evidence_intelligence artifacts", "central memory timeline", "telemetry"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
        "fix_needed": "Project jsonl artifacts are not canonical; timeline is source of truth",
    },
    "evidence": {
        "label": "Evidence / artifact register",
        "paths": ["server.py (/api/evidence/register)", "services/ledger.py"],
        "classification": "plugged",
        "reads": ["project evidence dir"],
        "writes": ["evidence files", "artifacts registry", "central memory"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
    },
    "coc_ledger": {
        "label": "COC / event ledger",
        "paths": ["services/ledger.py", "server.py (/api/coc/event*)"],
        "classification": "plugged",
        "reads": ["ledger.log"],
        "writes": ["data/ledger/ledger.log"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "medium",
        "duplicate_truth_risk": "medium",
        "fix_needed": "",
    },
    "learning": {
        "label": "Central learning",
        "paths": ["services/memory/learning.py"],
        "classification": "plugged",
        "reads": ["learning_state.json"],
        "writes": ["learning_state.json"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
    },
    "self_healing": {
        "label": "Self-healing (immune)",
        "paths": ["services/memory/self_healing.py"],
        "classification": "plugged",
        "reads": ["entities", "projects", "inquiries", "forensics", "rfq"],
        "writes": ["corrections.jsonl"],
        "read_before": True,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "none",
    },
    "rfq": {
        "label": "RFQ system",
        "paths": ["services/rfq.py"],
        "classification": "plugged",
        "reads": ["data/rfq/*.json"],
        "writes": ["data/rfq/", "ledger events"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "medium",
        "duplicate_truth_risk": "medium",
        "fix_needed": "",
    },
    "job_engine": {
        "label": "Background job engine",
        "paths": ["services/engine.py"],
        "classification": "plugged",
        "reads": ["data/jobs/"],
        "writes": ["projects/", "ledger", "emails"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "high",
        "duplicate_truth_risk": "high",
        "fix_needed": "",
    },
    "alerts": {
        "label": "Alerts / SLA",
        "paths": ["services/alerts.py", "services/alerts_center.py", "engine.check_slas"],
        "classification": "partial",
        "reads": ["process status", "alerts.jsonl"],
        "writes": ["alerts.jsonl", "ledger EXCEPTION events"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "medium",
        "duplicate_truth_risk": "low",
        "fix_needed": "SLA breach linked via engine adapter",
    },
    "emails": {
        "label": "Email transport",
        "paths": ["services/emails.py"],
        "classification": "plugged",
        "reads": [],
        "writes": ["SMTP transport + telemetry.jsonl signals"],
        "read_before": False,
        "write_after": True,
        "orphan_risk": "none",
        "duplicate_truth_risk": "none",
        "fix_needed": "Transport only; canonical truth in central memory telemetry",
    },
    "reports_export": {
        "label": "Reports / export / binder",
        "paths": ["services/reports.py", "services/acquisition/export.py", "analytics.py"],
        "classification": "plugged",
        "reads": ["projects/", "find_entity_id for context flag"],
        "writes": ["export bundles + telemetry signals"],
        "read_before": True,
        "write_after": True,
        "orphan_risk": "low",
        "duplicate_truth_risk": "low",
        "fix_needed": "",
    },
    "organism_sqlite": {
        "label": "organism/ sqlite subsystem",
        "paths": ["organism/"],
        "classification": "outside",
        "reads": ["organism/data/kyc.db"],
        "writes": ["organism/data/kyc.db"],
        "read_before": False,
        "write_after": False,
        "orphan_risk": "high",
        "duplicate_truth_risk": "high",
        "fix_needed": "LEGACY — not wired to central memory",
    },
    "ui_ops": {
        "label": "UI control / status / memory",
        "paths": ["ui/control.html", "ui/status.html", "ui/memory.html"],
        "classification": "plugged",
        "reads": ["/api/memory/*", "/api/projects"],
        "writes": [],
        "read_before": True,
        "write_after": False,
        "orphan_risk": "none",
        "duplicate_truth_risk": "none",
    },
    "health": {
        "label": "Health / readiness",
        "paths": ["server.py (/healthz, /health/ready)"],
        "classification": "plugged",
        "reads": ["filesystem checks", "self-heal orphan counts"],
        "writes": ["telemetry readiness/smtp/degraded signals"],
        "read_before": True,
        "write_after": True,
        "orphan_risk": "none",
        "duplicate_truth_risk": "none",
        "fix_needed": "",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_write_after_workflow(
    project_id: str,
    *,
    step_id: str = "",
    phase: str = "",
    email: str = "",
    base: Optional[Any] = None,
) -> None:
    """Workflow step/phase changes → central timeline."""
    try:
        eid = find_entity_id(project_id=project_id, email=email, base=base)
        if not eid:
            safe_register_orphan("workflow", "project", project_id, "No entity for workflow step", base=base)
            return
        _attach_entity_refs(eid, project_id=project_id, email=email, base=base)
        payload = {"step_id": step_id, "phase": phase}
        if step_id and not _timeline_has(eid, "workflow_step", ref_id=step_id, base=base):
            append_timeline(eid, "workflow_step", "project", project_id, payload, base)
        if phase and not _timeline_has(eid, "workflow_phase", ref_id=phase, base=base):
            append_timeline(eid, "workflow_phase", "project", project_id, {"phase": phase}, base)
        if step_id == "intake_received":
            record_learning_signal("workflow:intake_received", "inquiry_to_intake", success=True, base=base)
    except Exception as e:
        logger.warning("Central memory write (workflow): %s", e)


def safe_write_after_rfq(
    rfq_id: str,
    project_id: str,
    *,
    event_kind: str = "rfq_opened",
    category: str = "",
    base: Optional[Any] = None,
) -> None:
    try:
        eid = find_entity_id(project_id=project_id, base=base)
        if not eid:
            safe_register_orphan("rfq", "project", project_id, f"RFQ {rfq_id} without entity", base=base)
            return
        _attach_entity_refs(eid, project_id=project_id, base=base)
        add_ref_rfq = rfq_id
        from .entity_graph import add_ref

        add_ref(eid, "rfq", add_ref_rfq, base)
        if not _timeline_has(eid, event_kind, ref_id=rfq_id, base=base):
            append_timeline(
                eid,
                event_kind,
                "rfq",
                rfq_id,
                {"project_id": project_id, "category": category},
                base,
            )
    except Exception as e:
        logger.warning("Central memory write (rfq): %s", e)


def safe_write_after_acquisition_outcome(
    *,
    lead_id: str = "",
    project_id: str = "",
    org_key: str = "",
    stage: str,
    success: bool,
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Any] = None,
) -> None:
    """Bridge acquisition/intelligence outcomes into central memory."""
    try:
        eid = find_entity_id(
            lead_id=lead_id,
            project_id=project_id,
            company=org_key,
            base=base,
        )
        if not eid and org_key and "@" in org_key:
            eid = resolve_or_create_entity(email=org_key, base=base)
        if not eid:
            safe_register_orphan(
                "acquisition_outcome",
                "project" if project_id else "lead",
                project_id or lead_id or org_key,
                f"Outcome {stage} without entity",
                base=base,
            )
            return
        _attach_entity_refs(
            eid,
            project_id=project_id,
            lead_id=lead_id,
            base=base,
        )
        if not _timeline_has(eid, "outcome", ref_id=stage, base=base):
            link_outcome(
                eid,
                stage,
                success,
                lead_id=lead_id,
                project_id=project_id,
                metadata=metadata,
                base=base,
            )
        conv = {
            "inquiry_submitted": "lead_to_inquiry",
            "intake_completed": "inquiry_to_intake",
            "evidence_uploaded": "intake_to_evidence",
        }.get(stage)
        if conv and success:
            record_learning_signal(stage, conv, success=True, base=base)
    except Exception as e:
        logger.warning("Central memory write (acquisition outcome): %s", e)


def safe_write_after_forensic_event(
    event_type: str,
    project_id: str,
    org_key: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    base: Optional[Any] = None,
) -> None:
    try:
        eid = find_entity_id(project_id=project_id, company=org_key, base=base)
        if not eid:
            safe_register_orphan("forensics", "project", project_id, f"Forensic {event_type} unlinked", base=base)
            return
        ref_key = f"{event_type}:{project_id}"
        if not _timeline_has(eid, "forensic_event", ref_id=ref_key, base=base):
            append_timeline(
                eid,
                "forensic_event",
                "project",
                ref_key,
                {"event_type": event_type, "org_key": org_key, "project_id": project_id, **(payload or {})},
                base,
            )
    except Exception as e:
        logger.warning("Central memory write (forensic): %s", e)


def safe_write_after_coc_event(
    event: Dict[str, Any],
    base: Optional[Any] = None,
) -> None:
    """Link JSON COC events (non-form) into central memory."""
    try:
        project_id = ""
        for w in event.get("what") or []:
            if isinstance(w, dict) and w.get("id", "").startswith("P-"):
                project_id = w["id"]
                break
        evt_id = event.get("event_id", "")
        safe_link_ledger_event(
            evt_id,
            project_id,
            event_type=event.get("event_type", "ATTEST"),
            why=event.get("why", ""),
            base=base,
        )
    except Exception as e:
        logger.warning("Central memory write (coc event): %s", e)


def safe_write_after_job_kickoff(
    project_id: str,
    order_id: str,
    email: str,
    name: str,
    skus: List[str],
    event_id: str,
    base: Optional[Any] = None,
) -> None:
    try:
        from .central_memory import safe_link_after_kickoff

        safe_link_after_kickoff(project_id, order_id, email, name, skus, base=base)
        safe_link_ledger_event(
            event_id,
            project_id,
            email=email,
            name=name,
            event_type="ATTEST",
            why="Order paid; project created (job engine)",
            base=base,
        )
    except Exception as e:
        logger.warning("Central memory write (job kickoff): %s", e)


def safe_write_after_sla_event(project_id: str, event_id: str, why: str, base: Optional[Any] = None) -> None:
    try:
        safe_link_ledger_event(
            event_id,
            project_id,
            event_type="EXCEPTION",
            why=why,
            base=base,
        )
        eid = find_entity_id(project_id=project_id, base=base)
        if eid and not _timeline_has(eid, "sla_escalation", ref_id=project_id, base=base):
            append_timeline(eid, "sla_escalation", "project", project_id, {"why": why}, base)
            record_learning_signal("sla:breach", "lead_failed", success=False, base=base)
    except Exception as e:
        logger.warning("Central memory write (sla): %s", e)


def safe_write_after_evidence_intelligence(
    project_id: str,
    *,
    filename: str,
    artifact_id: str = "",
    sha256: str = "",
    classification: Optional[Dict[str, Any]] = None,
    entities: Optional[List[Dict[str, Any]]] = None,
    profile_delta: Optional[Dict[str, Any]] = None,
    gaps: Optional[List[str]] = None,
    status: str = "completed",
    base: Optional[Any] = None,
) -> None:
    """Bridge evidence intelligence into central memory timeline (canonical brain)."""
    try:
        eid = find_entity_id(project_id=project_id, base=base)
        if not eid:
            safe_register_orphan(
                "evidence_intelligence",
                "project",
                project_id,
                "Evidence analyzed without linked entity",
                base=base,
            )
            return
        ref = f"{filename}:{sha256[:12]}" if sha256 else filename
        if not _timeline_has(eid, "evidence_analyzed", ref_id=ref, base=base):
            append_timeline(
                eid,
                "evidence_analyzed",
                "project",
                project_id,
                {
                    "filename": filename,
                    "artifact_id": artifact_id,
                    "sha256": sha256[:16] if sha256 else "",
                    "status": status,
                },
                base,
            )
        if classification and classification.get("document_type") not in (None, "unknown"):
            cref = f"{filename}:{classification.get('document_type')}"
            if not _timeline_has(eid, "document_classified", ref_id=cref, base=base):
                append_timeline(
                    eid,
                    "document_classified",
                    "project",
                    project_id,
                    {
                        "filename": filename,
                        "document_type": classification.get("document_type"),
                        "confidence": classification.get("confidence"),
                    },
                    base,
                )
        if profile_delta and not _timeline_has(eid, "profile_inferred", ref_id=project_id, base=base):
            append_timeline(
                eid,
                "profile_inferred",
                "project",
                project_id,
                {"fields": list(profile_delta.keys()), "status": status},
                base,
            )
        for ent in entities or []:
            if float(ent.get("confidence", 0)) < 0.5:
                continue
            record_learning_signal(
                f"entity:{ent.get('type')}:{str(ent.get('value',''))[:40]}",
                "intake_to_evidence",
                success=True,
                paperwork_hint=ent.get("type", ""),
                base=base,
            )
        for gap_id in gaps or []:
            record_learning_signal(f"gap:{gap_id}", "intake_to_evidence", success=False, base=base)
            if not _timeline_has(eid, "gap_detected", ref_id=f"{project_id}:{gap_id}", base=base):
                append_timeline(
                    eid,
                    "gap_detected",
                    "project",
                    project_id,
                    {"gap_id": gap_id},
                    base,
                )
    except Exception as e:
        logger.warning("Central memory write (evidence intelligence): %s", e)


def safe_write_after_evidence_confirmation(
    project_id: str,
    field: str,
    value: str,
    status: str,
    base: Optional[Any] = None,
) -> None:
    try:
        eid = find_entity_id(project_id=project_id, base=base)
        if not eid:
            return
        append_timeline(
            eid,
            "confirmation_requested" if status == "unsure" else "profile_confirmed",
            "project",
            project_id,
            {"field": field, "value": value[:120], "status": status},
            base,
        )
        record_learning_signal(
            f"confirm:{field}:{status}",
            "intake_to_evidence",
            success=status == "confirmed",
            base=base,
        )
    except Exception as e:
        logger.warning("Central memory write (evidence confirmation): %s", e)


def safe_register_orphan(
    engine: str,
    ref_type: str,
    ref_id: str,
    detail: str,
    base: Optional[Any] = None,
) -> None:
    """Register missing linkage for self-healing (in-memory queue + corrections on scan)."""
    try:
        from .self_healing import register_orphan_warning

        register_orphan_warning(engine, ref_type, ref_id, detail, base=base)
    except Exception as e:
        logger.warning("Orphan register failed: %s", e)


def run_integration_audit(base: Optional[Any] = None) -> Dict[str, Any]:
    """Runtime audit snapshot for UI and tests."""
    from .self_healing import run_self_healing_scan

    heal = run_self_healing_scan(base=base, write_suggestions=False)
    plugged = []
    partial = []
    outside = []
    legacy = []
    duplicate_islands = []

    for eid, meta in ENGINE_REGISTRY.items():
        c = meta.get("classification", "outside")
        entry = {
            "id": eid,
            "label": meta.get("label", eid),
            "paths": meta.get("paths", []),
            "read_before": meta.get("read_before", False),
            "write_after": meta.get("write_after", False),
            "orphan_risk": meta.get("orphan_risk", ""),
            "duplicate_truth_risk": meta.get("duplicate_truth_risk", ""),
            "fix_needed": meta.get("fix_needed", ""),
        }
        if c == "plugged":
            plugged.append(entry)
        elif c == "partial":
            partial.append(entry)
        elif c == "legacy_inactive":
            legacy.append(entry)
        else:
            outside.append(entry)
        if meta.get("duplicate_truth_risk") == "high":
            duplicate_islands.append(entry)

    warnings = []
    if heal.get("orphan_projects"):
        warnings.append(f"{len(heal['orphan_projects'])} orphan projects")
    if heal.get("orphan_inquiries"):
        warnings.append(f"{len(heal['orphan_inquiries'])} orphan inquiries")
    if heal.get("unlinked_forensic_projects"):
        warnings.append(f"{len(heal['unlinked_forensic_projects'])} forensic projects without entity")
    if heal.get("unlinked_rfq_projects"):
        warnings.append(f"{len(heal['unlinked_rfq_projects'])} RFQ projects without entity")
    if heal.get("pending_orphans"):
        warnings.append(f"{len(heal['pending_orphans'])} pending engine orphans")

    critical_outside = [
        e for e in outside
        if e["id"] not in ("emails", "health", "reports_export", "ui_ops")
        and e.get("orphan_risk") in ("high", "medium")
    ]
    unified = len(critical_outside) == 0 and len(duplicate_islands) <= 1

    return {
        "audit_utc": _utc_now(),
        "verdict": "organism_unified" if unified else "organism_partial",
        "plugged": plugged,
        "partial": partial,
        "outside": outside,
        "legacy_inactive": legacy,
        "duplicate_memory_islands": duplicate_islands,
        "warnings": warnings,
        "self_healing": heal,
        "counts": {
            "plugged": len(plugged),
            "partial": len(partial),
            "outside": len(outside),
            "legacy": len(legacy),
        },
    }
