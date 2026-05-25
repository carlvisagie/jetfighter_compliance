"""
Operator cockpit — workflow steering from real project status + health signals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.config import DATA
from services.knowledge_index import topics_for_phase
from services.process import STEP_LIB, compute_status

# UI learning phase keys (contextual panels)
PHASE_GUIDANCE: Dict[str, Dict[str, Any]] = {
    "inquiry": {
        "title": "Inquiry phase",
        "explain": "A prospect submitted the readiness form. Your job is to confirm the project exists, links work, and the customer can reach intake.",
        "good_looks_like": "Project ID created, HTTPS intake URL in inquiry response, event in ledger.",
        "can_go_wrong": "Wrong PUBLIC_BASE_URL, missing intake secret, SMTP off (email links not sent).",
        "check": ["GET /health/ready shows inquiry_onboarding_active", "Open intake URL from inquiry response", "Event in /api/events/recent"],
        "next_action": "Verify inquiry event and send or test the intake link.",
        "why": "Without a valid intake path the customer cannot enter the compliance workflow.",
        "learn_phase": "inquiry",
        "links": [{"label": "Inquiry page", "href": "/ui/inquiry.html"}, {"label": "Owner checklist", "topic": "owner-activation-checklist"}],
    },
    "intake": {
        "title": "Intake phase",
        "explain": "Customer must complete the intake form with scope, contacts, and external flags.",
        "good_looks_like": "intake.json saved under project communications, workflow moves toward SCOPE.",
        "can_go_wrong": "Expired token, customer stuck on validation, incomplete external_flags.",
        "check": ["Open intake URL with token", "Submit test intake in staging", "Project folder has communications/intake.json"],
        "next_action": "Confirm intake submitted; advance workflow when intake_received step is done.",
        "why": "Intake locks what evidence and scope the binder must cover.",
        "learn_phase": "intake",
        "links": [{"label": "Status board", "href": "/ui/status.html"}, {"label": "Launch path", "topic": "launch-path"}],
    },
    "evidence": {
        "title": "Evidence & scope phase",
        "explain": "Lock scope with the client and gather policies, checklists, and artifacts for the binder.",
        "good_looks_like": "scope_locked and SKU-specific steps (CMMC gap / DPP model) marked done; uploads registered.",
        "can_go_wrong": "Scope creep, missing uploads, checklist items left PENDING.",
        "check": ["Required steps open in status board", "Upload UI used for artifacts", "Checklist matches SKUs"],
        "next_action": "Complete scope_locked and evidence collection steps before binder build.",
        "why": "Auditors and customers judge you on organized evidence, not promises.",
        "learn_phase": "evidence",
        "links": [{"label": "Upload", "href": "/ui/upload.html"}, {"label": "Event helper", "href": "/ui/event.html"}],
    },
    "binder": {
        "title": "Binder / export phase",
        "explain": "Assemble the evidence binder and export package for handover.",
        "good_looks_like": "evidence_binder_ready step done; export endpoint returns binder.",
        "can_go_wrong": "Export run before evidence complete; broken file paths in project dir.",
        "check": ["GET /api/project/{id}/export", "All required evidence steps done", "Handover checklist drafted"],
        "next_action": "Mark evidence_binder_ready done, run export, review binder contents.",
        "why": "The binder is the deliverable the customer pays for.",
        "learn_phase": "binder",
        "links": [{"label": "Export API", "href_pattern": "/api/project/{project_id}/export"}],
    },
    "handover": {
        "title": "Handover phase",
        "explain": "Client signs off on delivery; project moves to HANDOVER phase.",
        "good_looks_like": "handover_signed complete; RAG green; final CoC events logged.",
        "can_go_wrong": "Open required steps still amber/red; no final event in ledger.",
        "check": ["All required steps done", "Log handover event", "Archive project notes"],
        "next_action": "Mark handover_signed done and log final chain-of-custody event.",
        "why": "Closes the compliance engagement with auditable proof of delivery.",
        "learn_phase": "handover",
        "links": [{"label": "Event helper", "href": "/ui/event.html"}],
    },
    "event_logging": {
        "title": "Event logging",
        "explain": "Record chain-of-custody events for anything material that happened on a project.",
        "good_looks_like": "Events appear in ledger and /api/events/recent with correct project_id.",
        "can_go_wrong": "Wrong project id, missing why field, ops routes blocked without OPS_API_KEY.",
        "check": ["POST /api/coc/event or event form UI", "Recent events API", "Memory timeline after lookup"],
        "next_action": "Log what you just did before switching tasks.",
        "why": "Events are the forensic trail for disputes and audits.",
        "learn_phase": "event_logging",
        "links": [{"label": "Event helper", "href": "/ui/event.html"}, {"label": "Central memory", "topic": "central-memory"}],
    },
    "acquisition": {
        "title": "Acquisition (controlled MVP)",
        "explain": "Run a small cohort of real prospects through inquiry → intake — not bulk outreach.",
        "good_looks_like": "Targets tracked in data/acquisition/, manual approval before contact.",
        "can_go_wrong": "Automated spam, wrong segment, no end-to-end observation.",
        "check": ["onboarding_validation playbook", "Tracking CSVs updated", "Lead not marked approved without review"],
        "next_action": "Pick next approved lead and route to inquiry when ready.",
        "why": "Validates the business before scaling marketing spend.",
        "learn_phase": "acquisition",
        "links": [{"label": "Onboarding validation", "href": "/ui/onboarding_validation.html"}, {"label": "Controlled onboarding doc", "topic": "controlled-onboarding-acquisition"}],
    },
    "acquisition_discovery": {
        "title": "Lead discovery",
        "explain": "Import and score candidates from owner-approved CSV — no autonomous contact.",
        "good_looks_like": "review_queue.csv populated, scores documented, owner approves outreach.",
        "can_go_wrong": "Scraping, duplicate leads, outreach before approval.",
        "check": ["Run acquisition_import_candidates.py", "Open lead_discovery UI", "Review queue fit ≥ threshold"],
        "next_action": "Import CSV, review queue, approve only high-fit leads.",
        "why": "Keeps acquisition lawful and aligned with central memory.",
        "learn_phase": "acquisition_discovery",
        "links": [{"label": "Lead discovery UI", "href": "/ui/lead_discovery.html"}, {"label": "Lead discovery doc", "topic": "lead-discovery-engine"}],
    },
    "self_heal": {
        "title": "Self-heal & memory integrity",
        "explain": "Detect orphan projects, timeline gaps, and duplicate entities — suggestions only, never auto-delete.",
        "good_looks_like": "Orphan count trending down; entities linked after kickoff.",
        "can_go_wrong": "Ignoring orphan warnings; running heal on every page refresh in production.",
        "check": ["/api/memory/self-heal report", "Link entity after kickoff", "Memory lookup by project_id"],
        "next_action": "Review orphan list; link legacy projects or document exceptions.",
        "why": "Central memory must stay trustworthy for organism observability.",
        "learn_phase": "self_heal",
        "links": [{"label": "Intelligence page", "href": "/ui/memory.html"}, {"label": "Central memory doc", "topic": "central-memory"}],
    },
}

WORKFLOW_PHASE_TO_LEARN: Dict[str, str] = {
    "ORDER": "inquiry",
    "INTAKE": "intake",
    "SCOPE": "evidence",
    "BINDER": "binder",
    "HANDOVER": "handover",
}


def _project_meta(project_id: str) -> Dict[str, Any]:
    meta_path = DATA / "projects" / project_id / "meta.json"
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _resolve_learn_phase(wf_phase: str, next_step_id: Optional[str]) -> str:
    if next_step_id in ("order_ack", "intake_received"):
        return "inquiry" if next_step_id == "order_ack" else "intake"
    if next_step_id in ("scope_locked", "cmmc_gap", "dpp_model"):
        return "evidence"
    if next_step_id == "evidence_binder_ready":
        return "binder"
    if next_step_id == "handover_signed":
        return "handover"
    return WORKFLOW_PHASE_TO_LEARN.get(wf_phase, "event_logging")


def _next_open_step(steps: List[Dict]) -> Optional[Dict]:
    for s in steps:
        if s.get("required") and s.get("status") != "done" and s.get("opened_on") != "PENDING":
            return s
    for s in steps:
        if s.get("required") and s.get("status") != "done":
            return s
    return None


def build_cockpit(project_id: str = "", mode: str = "") -> Dict[str, Any]:
    """Build operator cockpit state from real workflow + optional mode override."""
    blockers: List[Dict[str, str]] = []
    pid = (project_id or "").strip()

    if not pid:
        pdir = DATA / "projects"
        if pdir.exists():
            dirs = sorted(pdir.glob("P-*"))
            if dirs:
                pid = dirs[-1].name

    status: Dict[str, Any] = {}
    if pid:
        try:
            status = compute_status(pid)
        except Exception:
            status = {}

    meta = _project_meta(pid) if pid else {}
    customer = meta.get("customer") or {}
    customer_label = customer.get("name") or customer.get("email") or "—"

    wf_phase = status.get("phase", "—") if status else "—"
    steps = status.get("steps") or []
    next_step = _next_open_step(steps)
    next_step_id = next_step["id"] if next_step else None
    next_title = next_step["title"] if next_step else "No open required step"
    overdue_steps = [
        s for s in steps if s.get("required") and s.get("status") != "done" and s.get("due_utc")
    ]
    # overdue filter handled in compute_status counts; list titles
    overdue_titles = []
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for s in steps:
        if s.get("required") and s.get("status") != "done" and s.get("due_utc") and s["due_utc"] < now:
            overdue_titles.append(s.get("title", s.get("id", "?")))

    if overdue_titles:
        blockers.append({"type": "overdue", "message": "Overdue: " + ", ".join(overdue_titles[:3])})

    learn_phase = (mode or "").strip().lower() or _resolve_learn_phase(wf_phase if wf_phase != "—" else "ORDER", next_step_id)

    guidance = dict(PHASE_GUIDANCE.get(learn_phase, PHASE_GUIDANCE["event_logging"]))
    if next_step_id and pid:
        guidance["next_action"] = f"Complete step: {next_title} ({next_step_id})"
        for link in guidance.get("links", []):
            if link.get("href_pattern"):
                link["href"] = link["href_pattern"].replace("{project_id}", pid)
                del link["href_pattern"]

    do_now = guidance["next_action"]
    if pid and next_step_id:
        do_now = f"[{pid}] {guidance['next_action']}"

    why = guidance.get("why", "")
    if status.get("rag") == "red":
        why = "RAG is red — overdue work puts customer delivery at risk. " + why
    elif status.get("rag") == "amber":
        why = "Required work is open — stay on the critical path. " + why

    import os

    if learn_phase in ("inquiry", "intake") and not os.getenv("SMTP_HOST"):
        blockers.append({"type": "smtp", "message": "SMTP not configured — intake emails may not send."})

    knowledge_topics = topics_for_phase(learn_phase)

    return {
        "project_id": pid or None,
        "customer_label": customer_label,
        "workflow_phase": wf_phase,
        "rag": status.get("rag"),
        "counts": status.get("counts"),
        "next_step": {"id": next_step_id, "title": next_title} if next_step_id else None,
        "blockers": blockers,
        "do_now": do_now,
        "why_it_matters": why,
        "learn_phase": learn_phase,
        "guidance": guidance,
        "knowledge_topic_ids": [t["id"] for t in knowledge_topics],
        "status_links": {
            "status_board": f"/ui/status.html?project={pid}" if pid else "/ui/status.html",
            "export": f"/api/project/{pid}/export" if pid else None,
            "advance_hint": "POST /api/project/{id}/advance with step_id" if pid else None,
        },
    }
