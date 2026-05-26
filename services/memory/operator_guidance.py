"""
Adaptive operator guidance — priorities, bottlenecks, attention, learning, organism state.
Uses real central memory, telemetry, workflow, and acquisition data only.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.config import DATA, PROJECTS
from services.operator_cockpit import build_cockpit
from services.process import compute_status
from services.production import readiness_checks

from .knowledge_index import contextual_lookup
from .learning import get_learning_summary
from .self_healing import run_self_healing_scan
from .telemetry import load_telemetry

SEVERITY_ORDER = ("green", "yellow", "orange", "red", "critical")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _max_severity(levels: List[str]) -> str:
    best = "green"
    for lv in SEVERITY_ORDER:
        if lv in levels:
            best = lv
    return best


def _project_list(limit: int = 50) -> List[str]:
    if not PROJECTS.exists():
        return []
    return sorted([p.name for p in PROJECTS.glob("P-*")])[-limit:]


def _has_intake(project_id: str) -> bool:
    p = DATA / "projects" / project_id / "communications" / "intake.json"
    return p.is_file()


def _evidence_count(project_id: str) -> int:
    ev = DATA / "projects" / project_id / "evidence"
    if not ev.is_dir():
        return 0
    return sum(1 for _ in ev.glob("*") if _.is_file())


def _scan_workflow_signals() -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Returns (stalled, overdue, intake_missing) project summaries."""
    stalled: List[Dict] = []
    overdue: List[Dict] = []
    intake_missing: List[Dict] = []
    now = _utcnow()

    for pid in _project_list(80):
        try:
            st = compute_status(pid)
        except Exception:
            continue
        meta_path = DATA / "projects" / pid / "meta.json"
        customer = "—"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                c = meta.get("customer") or {}
                customer = c.get("name") or c.get("email") or pid
            except Exception:
                customer = pid

        phase = st.get("phase", "ORDER")
        rag = st.get("rag", "green")
        steps = st.get("steps") or []
        open_required = [
            s for s in steps if s.get("required") and s.get("status") != "done" and s.get("opened_on") != "PENDING"
        ]

        if rag == "red":
            overdue.append(
                {
                    "type": "project",
                    "id": pid,
                    "label": customer,
                    "phase": phase,
                    "severity": "red",
                    "detail": "Overdue required workflow steps",
                }
            )

        if phase in ("ORDER", "INTAKE") and not _has_intake(pid):
            intake_missing.append(
                {
                    "type": "project",
                    "id": pid,
                    "label": customer,
                    "phase": phase,
                    "severity": "orange",
                    "detail": "Intake not completed",
                }
            )

        wf_path = DATA / "process" / f"{pid}.json"
        if wf_path.is_file():
            try:
                wf = json.loads(wf_path.read_text(encoding="utf-8"))
                created = _parse_ts((wf.get("workflow") or {}).get("created_utc", ""))
                if created and (now - created) > timedelta(days=7) and open_required:
                    stalled.append(
                        {
                            "type": "project",
                            "id": pid,
                            "label": customer,
                            "phase": phase,
                            "severity": "yellow" if rag != "red" else "red",
                            "detail": f"Open work for { (now - created).days }+ days",
                        }
                    )
            except Exception:
                pass

        if phase in ("SCOPE", "BINDER") and _evidence_count(pid) == 0 and open_required:
            stalled.append(
                {
                    "type": "project",
                    "id": pid,
                    "label": customer,
                    "phase": phase,
                    "severity": "orange",
                    "detail": "No evidence artifacts uploaded",
                }
            )

    return stalled, overdue, intake_missing


def _load_hot_leads(limit: int = 5) -> List[Dict]:
    try:
        from services.acquisition.storage import load_all_leads

        leads_dir = DATA / "acquisition" / "leads"
        if not leads_dir.exists():
            return []
        all_leads, _ = load_all_leads(leads_dir)
        ranked = sorted(
            all_leads,
            key=lambda l: (-(l.acquisition_priority_score or l.fit_score or 0), -(l.fit_score or 0)),
        )
        out = []
        for l in ranked[:limit]:
            if (l.fit_score or 0) < 50:
                continue
            out.append(
                {
                    "type": "lead",
                    "id": l.lead_id,
                    "label": l.company_name,
                    "fit_score": l.fit_score,
                    "status": l.status,
                    "segment": l.segment,
                    "severity": "yellow" if l.status == "new" else "green",
                    "detail": l.reason_summary or "High-fit lead in queue",
                }
            )
        return out
    except Exception:
        return []


def _acquisition_telemetry_age_hours(telemetry: List[Dict]) -> Optional[float]:
    acq = [t for t in telemetry if t.get("subsystem") == "acquisition"]
    if not acq:
        return None
    latest = max((_parse_ts(t.get("observed_at_utc") or "") for t in acq), key=lambda x: x or datetime.min.replace(tzinfo=timezone.utc))
    if not latest:
        return None
    return (_utcnow() - latest).total_seconds() / 3600.0


def _gather_context(project_id: str = "", mode: str = "") -> Dict[str, Any]:
    cockpit = build_cockpit(project_id=project_id, mode=mode)
    heal = run_self_healing_scan(write_suggestions=False)
    telemetry = load_telemetry(limit=250)
    learning = get_learning_summary()
    ready = readiness_checks()

    try:
        from .organism_observability import get_observability_dashboard

        obs = get_observability_dashboard(telemetry_limit=100)
    except Exception:
        obs = {"verdict": "not_observable", "subsystem_health": {}, "repeated_failures": []}

    stalled, overdue, intake_missing = _scan_workflow_signals()
    hot_leads = _load_hot_leads()
    smtp_ok = bool(ready.get("smtp_configured"))
    orphans = list(heal.get("orphan_projects") or [])
    tel_fails = [t for t in telemetry if t.get("success") is False]
    email_fails = [t for t in tel_fails if t.get("subsystem") == "email"]
    subsystems = obs.get("subsystem_health") or {}
    verdict = obs.get("verdict", "not_observable")
    acq_hours = _acquisition_telemetry_age_hours(telemetry)

    return {
        "cockpit": cockpit,
        "heal": heal,
        "telemetry": telemetry,
        "learning": learning,
        "ready": ready,
        "obs": obs,
        "stalled": stalled,
        "overdue": overdue,
        "intake_missing": intake_missing,
        "hot_leads": hot_leads,
        "smtp_ok": smtp_ok,
        "orphans": orphans,
        "tel_fails": tel_fails,
        "email_fails": email_fails,
        "subsystems": subsystems,
        "verdict": verdict,
        "acq_hours": acq_hours,
    }


def _compute_organism_state(ctx: Dict[str, Any]) -> str:
    if ctx["verdict"] == "not_observable":
        return "blind"
    if ctx["orphans"] and len(ctx["orphans"]) > 8:
        return "unstable"
    if ctx["obs"].get("repeated_failures"):
        return "unstable"
    if not ctx["smtp_ok"]:
        return "degraded"
    if ctx["overdue"]:
        return "blocked"
    if ctx["verdict"] == "partially_observable":
        return "degraded"
    conv = (ctx["learning"].get("conversion_counts") or {})
    if sum(conv.values()) > 0:
        return "learning"
    if len(ctx["telemetry"]) > 20:
        return "healthy"
    if ctx["verdict"] == "organism_observable":
        return "recovering"
    return "degraded"


def _build_bottlenecks(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    if not ctx["smtp_ok"]:
        items.append(
            {
                "id": "smtp",
                "title": "SMTP not configured",
                "severity": "red",
                "detail": "Onboarding and intake emails may not reach customers.",
                "category": "email",
            }
        )
    for p in ctx["intake_missing"][:5]:
        items.append(
            {
                "id": f"intake-{p['id']}",
                "title": f"Missing intake: {p['label']}",
                "severity": p["severity"],
                "detail": p["detail"],
                "category": "onboarding",
                "project_id": p["id"],
            }
        )
    for p in ctx["stalled"][:5]:
        items.append(
            {
                "id": f"stalled-{p['id']}",
                "title": f"Stalled: {p['label']}",
                "severity": p["severity"],
                "detail": p["detail"],
                "category": "workflow",
                "project_id": p["id"],
            }
        )
    if len(ctx["orphans"]) > 3:
        items.append(
            {
                "id": "orphans",
                "title": f"{len(ctx['orphans'])} orphan projects",
                "severity": "orange" if len(ctx["orphans"]) < 10 else "red",
                "detail": "Projects lack central memory entity links.",
                "category": "memory",
            }
        )
    if ctx["acq_hours"] is None or ctx["acq_hours"] > 72:
        items.append(
            {
                "id": "acquisition-starvation",
                "title": "Acquisition activity low",
                "severity": "yellow" if ctx["acq_hours"] and ctx["acq_hours"] < 168 else "orange",
                "detail": "No recent lead discovery telemetry in the last 72 hours.",
                "category": "acquisition",
            }
        )
    if len(ctx["telemetry"]) < 5:
        items.append(
            {
                "id": "telemetry-silence",
                "title": "Telemetry silence",
                "severity": "yellow",
                "detail": "Very few telemetry events — organism has limited visibility.",
                "category": "observability",
            }
        )
    if ctx["email_fails"]:
        items.append(
            {
                "id": "email-failures",
                "title": "Email delivery failures",
                "severity": "orange",
                "detail": f"{len(ctx['email_fails'])} failed email events in recent telemetry.",
                "category": "email",
            }
        )
    for sub, h in (ctx["subsystems"] or {}).items():
        if h.get("status") == "unhealthy":
            items.append(
                {
                    "id": f"sub-{sub}",
                    "title": f"Subsystem degraded: {sub}",
                    "severity": "orange",
                    "detail": f"Success rate {round((h.get('success_rate') or 0) * 100)}%",
                    "category": "subsystem",
                }
            )

    return items


def _build_recommendations(ctx: Dict[str, Any], bottlenecks: List[Dict]) -> Dict[str, List[str]]:
    immediate: List[str] = []
    short_term: List[str] = []
    strategic: List[str] = []

    if not ctx["smtp_ok"]:
        immediate.append("Configure SMTP on production so intake links reach customers by email.")
    for p in ctx["overdue"][:3]:
        immediate.append(f"Clear overdue workflow on {p['id']} ({p['label']}) — customer delivery is at risk.")
    if len(ctx["intake_missing"]) >= 3:
        short_term.append(f"{len(ctx['intake_missing'])} projects stalled at intake — follow up with customers.")
    if ctx["acq_hours"] is None or (ctx["acq_hours"] and ctx["acq_hours"] > 72):
        short_term.append("No new leads discovered recently — run lead import and review the queue.")
    if len(ctx["telemetry"]) < 10:
        short_term.append("Acquisition telemetry too low to evaluate scoring quality — run discovery import.")
    if len(ctx["orphans"]) > 5:
        strategic.append("Orphan project spike — link historical projects in central memory or document exceptions.")
    if ctx["verdict"] == "not_observable":
        strategic.append("Increase subsystem traffic so observability can reach organism_observable verdict.")
    for r in (ctx["obs"].get("recommended_improvements") or [])[:3]:
        if r not in strategic:
            strategic.append(r)

    return {"immediate": immediate[:6], "short_term": short_term[:6], "strategic": strategic[:6]}


def _infer_triggers(ctx: Dict[str, Any], bottlenecks: List[Dict]) -> List[str]:
    triggers: List[str] = []
    if not ctx["smtp_ok"] or ctx["email_fails"]:
        triggers.append("smtp_failure")
    if ctx["intake_missing"] or ctx["stalled"]:
        triggers.append("intake_stalled")
        triggers.append("lead_stalled")
    if ctx["orphans"]:
        triggers.append("workflow_orphan")
    if any(b.get("category") == "workflow" and "evidence" in (b.get("detail") or "").lower() for b in bottlenecks):
        triggers.append("evidence_gap")
    if any(b.get("id") == "telemetry-silence" for b in bottlenecks):
        triggers.append("telemetry_silence")
    if any(b.get("id") == "acquisition-starvation" for b in bottlenecks):
        triggers.append("acquisition_starvation")
    if not triggers:
        triggers.append("new_operator")
    return list(dict.fromkeys(triggers))


def build_operator_guidance(project_id: str = "", mode: str = "") -> Dict[str, Any]:
    ctx = _gather_context(project_id, mode)
    cockpit = ctx["cockpit"]
    bottlenecks = _build_bottlenecks(ctx)
    recs = _build_recommendations(ctx, bottlenecks)
    triggers = _infer_triggers(ctx, bottlenecks)

    learn_phase = cockpit.get("learn_phase") or "event_logging"
    recommended_learning = contextual_lookup(triggers=triggers, phase=learn_phase, limit=8)

    severities = [b["severity"] for b in bottlenecks] or ["green"]
    if ctx["overdue"]:
        severities.append("red")
    priority_level = _max_severity(severities)

    next_actions: List[Dict[str, Any]] = []
    if recs["immediate"]:
        next_actions.append(
            {
                "action": recs["immediate"][0],
                "timeframe": "now",
                "severity": priority_level,
                "if_ignored": "Customer onboarding or delivery may stall.",
            }
        )
    elif cockpit.get("do_now"):
        next_actions.append(
            {
                "action": cockpit["do_now"],
                "timeframe": "today",
                "severity": priority_level,
                "if_ignored": "Workflow drift increases rework and audit risk.",
            }
        )

    for r in recs["immediate"][1:3]:
        next_actions.append(
            {"action": r, "timeframe": "today", "severity": "orange", "if_ignored": "Issue may worsen."}
        )

    blocked_items = [
        {"type": b.get("category"), "title": b["title"], "detail": b["detail"], "severity": b["severity"]}
        for b in bottlenecks
        if b["severity"] in ("red", "orange", "critical")
    ]

    why_this_matters: List[str] = []
    if cockpit.get("why_it_matters"):
        why_this_matters.append(cockpit["why_it_matters"])
    if not ctx["smtp_ok"]:
        why_this_matters.append("Email is the primary path for customers to receive intake links after inquiry.")
    if ctx["overdue"]:
        why_this_matters.append("Overdue steps mean promised timelines are at risk.")
    if ctx["orphans"]:
        why_this_matters.append("Orphan projects weaken forensic reconstruction and organism observability.")

    attention: List[Dict] = []
    if ctx["hot_leads"]:
        attention.append({**ctx["hot_leads"][0], "role": "hottest_lead"})
    if ctx["overdue"]:
        attention.append({**ctx["overdue"][0], "role": "most_urgent_workflow"})
    elif ctx["stalled"]:
        attention.append({**ctx["stalled"][0], "role": "stalled_onboarding"})
    if cockpit.get("project_id"):
        attention.append(
            {
                "type": "project",
                "id": cockpit["project_id"],
                "label": cockpit.get("customer_label"),
                "role": "active_project",
                "phase": cockpit.get("workflow_phase"),
            }
        )
    neglected = [p for p in ctx["stalled"] if p not in ctx["overdue"]][:2]
    for n in neglected:
        attention.append({**n, "role": "neglected_project"})

    organism_state = _compute_organism_state(ctx)
    confidence = min(
        1.0,
        0.35
        + (0.15 if ctx["telemetry"] else 0)
        + (0.15 if ctx["subsystems"] else 0)
        + (0.15 if cockpit.get("project_id") else 0)
        + (0.1 if ctx["hot_leads"] else 0)
        + (0.1 if not ctx["orphans"] else 0),
    )

    primary = next_actions[0] if next_actions else {
        "action": "Review organism health and pick the highest-severity bottleneck.",
        "timeframe": "today",
        "severity": priority_level,
        "if_ignored": "Operational drift accumulates silently.",
    }

    return {
        "priority_level": priority_level,
        "next_actions": next_actions,
        "blocked_items": blocked_items,
        "why_this_matters": why_this_matters[:6],
        "recommended_learning": recommended_learning,
        "attention_targets": attention[:8],
        "organism_state": organism_state,
        "confidence": round(confidence, 2),
        "priority_command": {
            "most_important_action": primary["action"],
            "why": why_this_matters[0] if why_this_matters else cockpit.get("why_it_matters", ""),
            "if_ignored": primary.get("if_ignored", ""),
            "timeframe": primary.get("timeframe", "today"),
            "severity": primary.get("severity", priority_level),
        },
        "bottlenecks": bottlenecks,
        "recommendations": recs,
        "organism_summary": {
            "state": organism_state,
            "verdict": ctx["verdict"],
            "entity_count": ctx["heal"].get("entity_count", 0),
            "orphan_count": len(ctx["orphans"]),
            "telemetry_events": len(ctx["telemetry"]),
            "smtp_configured": ctx["smtp_ok"],
        },
        "cockpit": cockpit,
        "generated_utc": _ts(),
    }


def get_bottlenecks(project_id: str = "", mode: str = "") -> Dict[str, Any]:
    g = build_operator_guidance(project_id, mode)
    return {"ok": True, "bottlenecks": g["bottlenecks"], "generated_utc": g["generated_utc"]}


def get_attention(project_id: str = "", mode: str = "") -> Dict[str, Any]:
    g = build_operator_guidance(project_id, mode)
    return {"ok": True, "attention_targets": g["attention_targets"], "generated_utc": g["generated_utc"]}


def get_learning_guidance(project_id: str = "", mode: str = "", query: str = "") -> Dict[str, Any]:
    g = build_operator_guidance(project_id, mode)
    phase = g["cockpit"].get("learn_phase", "")
    items = list(g["recommended_learning"])
    if query:
        extra = contextual_lookup(phase=phase, query=query, limit=6)
        seen = {x["id"] for x in items}
        for e in extra:
            if e["id"] not in seen:
                items.append(e)
    return {
        "ok": True,
        "learn_phase": phase,
        "articles": items,
        "why_now": g["why_this_matters"][:3],
        "generated_utc": g["generated_utc"],
    }


def get_organism_state_view(project_id: str = "", mode: str = "") -> Dict[str, Any]:
    g = build_operator_guidance(project_id, mode)
    return {
        "ok": True,
        "organism_state": g["organism_state"],
        "summary": g["organism_summary"],
        "priority_level": g["priority_level"],
        "confidence": g["confidence"],
        "generated_utc": g["generated_utc"],
    }
