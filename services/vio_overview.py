"""VIO 2.0 — aggregate company awareness data for the visual timeline interface.

Pipeline backbone (the 7 stages every company traces through):

    intake → classification → validation → evidence mapping → review
            → approval → conversion

Plus a single branch:

    evidence mapping ──▶ client follow-up   (returns to evidence mapping
                                              once the customer responds)

See ``docs/VIO_DOCTRINE.md`` for the full visual-language doctrine.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ── Pipeline backbone (the 7-stage doctrine) ──────────────────────────────────
# Order matters — index is what the front-end uses to place the live point on
# each company's trace.
STAGE_BACKBONE: List[str] = [
    "intake",
    "classification",
    "validation",
    "evidence_mapping",
    "review",
    "approval",
    "conversion",
]
# Branch that hangs off ``evidence_mapping`` — the company is "off the spine"
# until the customer responds and we re-enter ``evidence_mapping``.
STAGE_BRANCH_CLIENT_FOLLOWUP = "client_followup"


# ── state priority (lower = more urgent) ──────────────────────────────────────
_STATE_PRIORITY = {
    "error": 0,
    "stuck": 1,
    "gap": 2,
    "waiting": 3,
    "analyzing": 4,
    "active": 5,
    "payment_pending": 6,
    "new": 7,
    "complete": 8,
}


# ── Stage-state lexicon (doctrine §2) ──────────────────────────────────────────
# Maps the operator-facing visual semantic to the canonical token the front-end
# can switch on. The front-end is allowed to render stillness for "healthy" and
# discrete deviation for everything else.
STAGE_STATE_HEALTHY = "healthy"
STAGE_STATE_STALLED = "stalled"
STAGE_STATE_FAILED = "failed"
STAGE_STATE_WAITING_CLIENT = "waiting_client"
STAGE_STATE_INCONSISTENT = "inconsistent"
STAGE_STATE_DONE = "done"
# Hours after which a company sitting in one stage starts to look stalled.
_STAGE_STALL_HOURS = 48.0


def _ts_age_hours(utc_str: str) -> float:
    """Return how many hours ago a UTC ISO string was."""
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return 0.0


def _stage_age_hours(row: Dict) -> float:
    """Hours since the company last *moved* (not since the intake was created).

    Doctrine §4 reads ``days_in_stage`` as how long the company has been
    sitting in its current stage — i.e. time since the most recent
    operator/customer/system event that touched the intake. Using
    ``created_utc`` (intake birth) instead inflates urgency for old
    customers that are actively progressing and under-inflates it for new
    customers that already stalled out.

    Falls back to ``created_utc`` only when no movement timestamp exists.
    """
    candidate = row.get("last_movement_utc") or ""
    if candidate:
        return _ts_age_hours(str(candidate))
    return _ts_age_hours(
        str(row.get("created_utc") or row.get("submitted_utc") or "")
    )


def _initials(name: str) -> str:
    parts = (_clean_company_name(name) or "?").split()
    return "".join(p[0].upper() for p in parts[:2]) or "?"


# ── Company-name sanitiser ────────────────────────────────────────────────────
_URL_LIKE = re.compile(r"^\s*https?://", re.IGNORECASE)
_BARE_DOMAIN = re.compile(r"^\s*(www\.)?[\w-]+\.[a-z]{2,}(/|$)", re.IGNORECASE)


def _clean_company_name(raw: Optional[str]) -> str:
    """Defensive sanitiser — VIO never displays a URL or empty string as a name.

    Customers occasionally paste a URL into the company-name field, and some
    historical pipelines copied URL fragments into ``company_name``. VIO is
    the operator's primary view — it must never present garbage. We accept
    the input but return a *display-safe* string:

        ``"http://www.example.com/path"``  →  ``"example.com"``
        ``"   "``                          →  ``"Unknown"``
        ``"Acme Corp"``                    →  ``"Acme Corp"``  (untouched)
    """
    if not raw:
        return "Unknown"
    s = str(raw).strip()
    if not s:
        return "Unknown"
    if _URL_LIKE.match(s) or _BARE_DOMAIN.match(s):
        # Reduce to the apex domain — best human-readable substitute.
        try:
            from urllib.parse import urlparse
            parsed = urlparse(s if "://" in s else f"http://{s}")
            host = (parsed.netloc or parsed.path or "").split("/")[0]
            host = host.replace("www.", "").strip().lower()
            return host or "Unknown"
        except Exception:
            return "Unknown"
    # Trim absurdly long names (likely paste-error)
    if len(s) > 120:
        return s[:117] + "…"
    return s


def _calc_state(row: Dict, ei: Dict) -> str:
    review_status = row.get("review_status", "")

    # EI-derived counts; fall back to intake-queue classification when no project
    files_up      = ei.get("files_uploaded", 0) or int(row.get("file_count") or 0)
    files_an      = ei.get("files_analyzed", 0)
    failures      = ei.get("extraction_failures", 0)
    pending       = ei.get("pending_analysis", 0)
    confirm_needed = len(ei.get("confirmation_needed") or [])
    # Gap count: EI primary, intake classification missing_items as fallback
    gaps = ei.get("missing_item_count", 0) or len(row.get("missing_items") or [])

    # ── Status-driven states (highest priority) ────────────────────────────────
    if review_status == "archived":
        return "complete"
    if review_status in ("approved", "payment_sent", "verified_complete"):
        return "payment_pending"
    # Operator flagged as waiting on customer / needs clarification
    if review_status in ("needs_info", "abandoned_upload", "partial_upload"):
        return "waiting"
    # Operator flagged as high-value / complex = significant gaps detected
    if review_status == "high_value":
        return "gap"

    # ── Evidence-intelligence-driven states ────────────────────────────────────
    if failures > 0:
        return "error"
    if confirm_needed:
        return "waiting"
    if files_up > 0 and gaps > 0:
        return "gap"
    if files_up > 0 and (files_an < files_up or pending > 0):
        return "analyzing"
    if files_up > 0:
        return "active"

    # Stale pending_review with no uploads → stuck
    age = _ts_age_hours(row.get("created_utc") or row.get("submitted_utc") or "")
    if age > 48 and review_status == "pending_review":
        return "stuck"
    return "new"


def _build_timeline(row: Dict, ei: Dict, state: str) -> List[Dict]:
    segments: List[Dict] = []

    # 1. Intake always present
    segments.append({
        "type": "intake",
        "status": "complete",
        "label": "Intake received",
        "utc": row.get("created_utc") or row.get("submitted_utc") or "",
        "detail": {
            "company": row.get("company_name") or row.get("company"),
            "email": row.get("contact_email") or row.get("email"),
            "review_status": row.get("review_status"),
        },
    })

    # 2. Documents uploaded
    files_up = ei.get("files_uploaded", 0)
    if files_up:
        doc_types = ei.get("document_types") or []
        up_status = "complete" if ei.get("files_analyzed", 0) > 0 else "active"
        if ei.get("extraction_failures", 0):
            up_status = "error"
        segments.append({
            "type": "upload",
            "status": up_status,
            "label": f"{files_up} file{'s' if files_up != 1 else ''} uploaded",
            "detail": {
                "files_uploaded": files_up,
                "files_analyzed": ei.get("files_analyzed", 0),
                "pending": ei.get("pending_analysis", 0),
                "failures": ei.get("extraction_failures", 0),
                "doc_types": [
                    {"file": d.get("file"), "type": d.get("type"), "confidence": d.get("confidence")}
                    for d in doc_types[:10]
                ],
            },
        })

    # 3. Analysis complete
    if ei.get("files_analyzed", 0):
        profile = ei.get("profile") or {}
        segments.append({
            "type": "analysis",
            "status": "complete",
            "label": f"{ei['files_analyzed']} analyzed",
            "detail": {
                "entity_count": ei.get("entity_count", 0),
                "company_names": (profile.get("company_names") or [])[:3],
                "emails": (profile.get("emails") or [])[:3],
                "technologies": (profile.get("technologies") or [])[:5],
                "compliance_references": (profile.get("compliance_references") or [])[:5],
            },
        })

    # 4. Gaps
    gaps = ei.get("gaps") or []
    if gaps:
        high = [g for g in gaps if g.get("priority") == "high"]
        segments.append({
            "type": "gap",
            "status": "active" if state not in ("complete",) else "resolved",
            "label": f"{len(gaps)} gap{'s' if len(gaps) != 1 else ''} — {len(high)} high priority",
            "detail": {
                "gaps": [
                    {"id": g.get("gap_id"), "label": g.get("label"), "priority": g.get("priority")}
                    for g in gaps[:8]
                ],
            },
        })

    # 5. Customer confirmation needed
    confirm = ei.get("confirmation_needed") or []
    if confirm:
        segments.append({
            "type": "confirmation",
            "status": "waiting",
            "label": f"{len(confirm)} item{'s' if len(confirm) != 1 else ''} need confirmation",
            "detail": {
                "items": [
                    {"field": c.get("field"), "value": c.get("value"), "status": c.get("status")}
                    for c in confirm[:5]
                ],
            },
        })

    # 6. Payment
    if row.get("review_status") in ("approved", "payment_sent", "archived"):
        segments.append({
            "type": "payment",
            "status": "complete" if row.get("review_status") == "archived" else "active",
            "label": "Payment link dispatched",
            "detail": {"review_status": row.get("review_status")},
        })

    # 7. Extraction errors (inline warning node)
    if ei.get("extraction_failures", 0):
        segments.append({
            "type": "error",
            "status": "error",
            "label": f"{ei['extraction_failures']} extraction failure{'s' if ei['extraction_failures'] != 1 else ''}",
            "detail": {
                "unsupported": (ei.get("unsupported_files") or [])[:5],
            },
        })

    # 8. Complete
    if row.get("review_status") == "archived":
        segments.append({
            "type": "complete",
            "status": "complete",
            "label": "Engagement complete",
            "detail": {},
        })

    return segments


def _priority_score(state: str, created_utc: str) -> float:
    """Lower is more urgent — used for secondary sort within same state.

    Preserved for backward compatibility with existing callers; the canonical
    sort key going forward is ``urgency_score`` (higher = more urgent).
    """
    age = _ts_age_hours(created_utc)
    return _STATE_PRIORITY.get(state, 9) * 1000 - age


# ── Stage classification ──────────────────────────────────────────────────────
def _classify_stage(row: Dict, ei: Dict, state: str) -> Dict[str, Any]:
    """Map an intake/EI snapshot to one of the 7 backbone stages.

    Returns ``{stage, stage_index, stage_state, on_branch, branch_label}``.
    """
    review_status = (row.get("review_status") or "").lower()
    files_up = ei.get("files_uploaded", 0) or int(row.get("file_count") or 0)
    files_an = int(ei.get("files_analyzed") or 0)
    failures = int(ei.get("extraction_failures") or 0)
    classified = bool(row.get("primary_category") or (ei.get("profile") or {}).get("company_names"))

    # ── Stage index ────────────────────────────────────────────────────────
    if review_status == "archived":
        stage = "conversion"
    elif review_status in ("approved", "payment_sent", "verified_complete"):
        stage = "approval"
    elif files_an > 0 and files_an >= files_up and not failures:
        # All uploaded files have been mapped — operator is the gate now.
        stage = "review"
    elif files_up > 0:
        # We have files but they haven't all been mapped yet.
        if classified and (failures or files_an > 0):
            stage = "evidence_mapping"
        elif classified:
            stage = "validation"
        else:
            stage = "classification"
    else:
        stage = "intake"

    # ── Branch detection ──────────────────────────────────────────────────
    on_branch = False
    branch_label = ""
    if review_status in ("needs_info", "abandoned_upload", "partial_upload"):
        on_branch = True
        branch_label = "client follow-up"
    elif ei.get("confirmation_needed"):
        # Waiting on the customer to confirm extracted entities.
        on_branch = True
        branch_label = "client follow-up"

    # ── Stage state (the visual deviation) ────────────────────────────────
    if state == "complete":
        stage_state = STAGE_STATE_DONE
    elif state == "error" or failures > 0:
        stage_state = STAGE_STATE_FAILED
    elif on_branch:
        stage_state = STAGE_STATE_WAITING_CLIENT
    elif state == "stuck":
        stage_state = STAGE_STATE_STALLED
    elif state == "gap":
        # Gap means evidence mapping flagged missing items — visible deviation
        # but the line itself is still moving; surface it as inconsistent.
        stage_state = STAGE_STATE_INCONSISTENT
    else:
        # Default healthy unless aging in stage too long. We use stage-age
        # (time since the last movement) not intake-age, otherwise every
        # company older than 48h would render as stalled — see
        # docs/VIO_DOCTRINE.md §3 (stalled = "sitting in stage > 48h with
        # no movement").
        if _stage_age_hours(row) > _STAGE_STALL_HOURS and stage != "conversion":
            stage_state = STAGE_STATE_STALLED
        else:
            stage_state = STAGE_STATE_HEALTHY

    return {
        "stage": stage,
        "stage_index": STAGE_BACKBONE.index(stage),
        "stage_state": stage_state,
        "on_branch": on_branch,
        "branch_label": branch_label,
    }


def _build_attention(row: Dict, ei: Dict, stage_info: Dict[str, Any]) -> List[str]:
    """Short, terse facts the operator needs to know — at most a few items.

    These ride along the line as small marks. They are NOT decoration; each
    entry must map to a real condition that warrants operator awareness.
    """
    facts: List[str] = []
    failures = int(ei.get("extraction_failures") or 0)
    if failures:
        facts.append(f"{failures} extraction failure" + ("s" if failures != 1 else ""))
    gaps = int(ei.get("missing_item_count") or 0) or len(row.get("missing_items") or [])
    if gaps:
        facts.append(f"{gaps} evidence gap" + ("s" if gaps != 1 else ""))
    confirm = len(ei.get("confirmation_needed") or [])
    if confirm:
        facts.append(f"{confirm} need confirmation")
    if stage_info["on_branch"]:
        facts.append("awaiting customer reply")
    if stage_info["stage_state"] == STAGE_STATE_STALLED:
        age_h = _stage_age_hours(row)
        facts.append(f"in stage ~{int(age_h)}h")
    return facts[:4]


def _compute_urgency(row: Dict, ei: Dict, stage_info: Dict[str, Any]) -> int:
    """Higher = more urgent. Drives the top-down ordering in Level 1.

    Formula (doctrine §3):
        failure_flags × 1000
      + days_in_stage × 50
      + gap_count × 10
      + stale_payment_days × 5
      − completion_credit
    """
    failures = int(ei.get("extraction_failures") or 0)
    gaps = int(ei.get("missing_item_count") or 0) or len(row.get("missing_items") or [])
    age_h = _stage_age_hours(row)
    days_in_stage = max(0, age_h / 24.0)

    stale_payment_days = 0
    if (row.get("review_status") or "").lower() in ("payment_sent", "approved"):
        # Payment sent but not converted — every day this drifts adds urgency.
        stale_payment_days = days_in_stage

    score = (
        failures * 1000
        + days_in_stage * 50
        + gaps * 10
        + stale_payment_days * 5
    )
    if stage_info["stage_state"] == STAGE_STATE_DONE:
        # Completed companies are still listed (operator may want to revisit)
        # but always last.
        score = -1
    return int(score)


def _build_company_row(row: Dict, ei: Dict) -> Dict:
    intake_id = row.get("intake_id") or ""
    project_id = row.get("project_id") or ""
    # Prefer intake_id as the row key so VIO can call /api/operator/vio/company/{intake_id}
    pid = intake_id or project_id
    raw_name = row.get("company_name") or row.get("company") or ""
    name = _clean_company_name(raw_name)
    state = _calc_state(row, ei)
    timeline = _build_timeline(row, ei, state)
    created = row.get("created_utc") or row.get("submitted_utc") or ""
    age_h = _ts_age_hours(created)
    stage_age_h = _stage_age_hours(row)

    stage_info = _classify_stage(row, ei, state)
    attention = _build_attention(row, ei, stage_info)
    urgency = _compute_urgency(row, ei, stage_info)

    return {
        "project_id": project_id,
        "intake_id": intake_id,
        "row_id": pid,
        "company_name": name,
        "initials": _initials(name),
        "contact_email": row.get("contact_email") or row.get("email") or "",
        "contact_phone": row.get("contact_phone") or row.get("phone") or "",
        "created_utc": created,
        "last_movement_utc": row.get("last_movement_utc") or "",
        "age_hours": round(age_h, 1),
        "review_status": row.get("review_status") or "",
        "state": state,
        "priority_score": _priority_score(state, created),
        # ── Doctrine fields (Level 1 unified-line rendering) ────────────
        "stage": stage_info["stage"],
        "stage_index": stage_info["stage_index"],
        "stage_state": stage_info["stage_state"],
        "on_branch": stage_info["on_branch"],
        "branch_label": stage_info["branch_label"],
        "urgency_score": urgency,
        # Time spent in the current stage — what the doctrine formula
        # actually means. Falls back to intake-age only when no movement
        # timestamp has been recorded yet.
        "days_in_stage": round(stage_age_h / 24.0, 2),
        "attention": attention,
        # ── Legacy fields (kept for back-compat with existing detail panel) ──
        "timeline": timeline,
        "quick_stats": {
            "files_uploaded": ei.get("files_uploaded", 0) or int(row.get("file_count") or 0),
            "files_analyzed": ei.get("files_analyzed", 0),
            "gaps": ei.get("missing_item_count", 0) or len(row.get("missing_items") or []),
            "failures": ei.get("extraction_failures", 0),
            "pending": ei.get("pending_analysis", 0),
            "confirmation_needed": len(ei.get("confirmation_needed") or []),
            "entity_count": ei.get("entity_count", 0),
        },
        "next_action": ((ei.get("next_actions") or [None])[0]),
        "ei_ok": ei.get("ok", False),
    }


def build_vio_overview(limit: int = 60, *, include_organism: bool = True) -> Dict:
    """Aggregate all company rows for VIO 2.0 rendering.

    Args:
      limit: max companies to return.
      include_organism: when False, skip the organism awareness summary.
        This MUST be False when called from inside the organism's own
        VioCollector to avoid infinite recursion.
    """
    from services.intake.queue import get_operator_review_queue

    try:
        queue_data = get_operator_review_queue(limit=min(limit, 100), include_archived=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "companies": [], "organism_health": {}}

    rows = queue_data.get("queue") or []
    companies: List[Dict] = []

    for row in rows:
        pid = row.get("project_id") or row.get("intake_id") or ""
        ei: Dict = {}
        if pid:
            try:
                from services.evidence_intelligence import get_operator_evidence_intelligence
                ei = get_operator_evidence_intelligence(pid) or {}
            except Exception:
                ei = {}
        companies.append(_build_company_row(row, ei))

    # Doctrine §3: top-down ordering by urgency descending. Done companies
    # always sink to the bottom (their urgency_score is -1).
    companies.sort(key=lambda c: (-c["urgency_score"], c.get("priority_score", 0)))

    state_counts: Dict[str, int] = {}
    stage_counts: Dict[str, int] = {s: 0 for s in STAGE_BACKBONE}
    for c in companies:
        s = c["state"]
        state_counts[s] = state_counts.get(s, 0) + 1
        st = c.get("stage")
        if st in stage_counts:
            stage_counts[st] += 1

    payload: Dict = {
        "ok": True,
        "companies": companies,
        "organism_health": {
            "total": len(companies),
            **state_counts,
        },
        "stage_backbone": STAGE_BACKBONE,
        "stage_counts": stage_counts,
        "queue_depth": queue_data.get("queue_depth", 0),
        "urgent_count": queue_data.get("urgent_count", 0),
    }
    if include_organism:
        payload["organism"] = _organism_summary()
    return payload


# ── TTL cache for organism awareness ─────────────────────────────────────────
# The residue scan walks the whole repo (~seconds). VIO's auto-refresh fires
# every 60s, so caching for 45s is invisible to the operator and removes
# repeated scan cost across page loads.
_ORGANISM_TTL_SECONDS = 45.0
_organism_cache: Dict[str, Any] = {"ts": 0.0, "payload": None}


def _organism_summary(*, force: bool = False) -> Dict[str, Any]:
    """Compact organism awareness for the VIO header strip.

    Fails silently — VIO must still render if the organism layer is unavailable.
    Result is cached for ``_ORGANISM_TTL_SECONDS`` to avoid repeated whole-repo
    residue scans on every overview request.
    """
    import time

    now = time.time()
    cached = _organism_cache.get("payload")
    if not force and cached is not None and (now - _organism_cache.get("ts", 0.0)) < _ORGANISM_TTL_SECONDS:
        return dict(cached)

    try:
        from services.organism_state import compute_organism_state
        state = compute_organism_state()
    except Exception as exc:
        fail = {
            "available": False,
            "error": str(exc),
            "health_state": "UNKNOWN",
        }
        _organism_cache["payload"] = fail
        _organism_cache["ts"] = now
        return dict(fail)

    sigs = state.get("signals") or {}
    intake_sig = sigs.get("intake") or {}
    storage_sig = sigs.get("storage") or {}

    # Surface the most important reconciliation mismatches as a flat list
    mismatches: List[Dict] = []
    for chk in state.get("checks") or []:
        if not isinstance(chk, dict):
            continue
        if chk.get("ok"):
            continue
        mismatches.append({
            "name": chk.get("name") or "",
            "severity": chk.get("severity") or "info",
            "detail": chk.get("detail") or "",
        })

    payload = {
        "available": True,
        "health_state": state.get("health_state", "UNKNOWN"),
        "current_bottleneck": state.get("current_bottleneck"),
        "next_recommended_action": state.get("next_recommended_action"),
        "mismatches": mismatches[:10],
        "mismatch_count": len(mismatches),
        "queue_depth": int(intake_sig.get("queue_depth") or state.get("queue_depth") or 0),
        "intake_count_active": int(intake_sig.get("intake_count_active") or state.get("intake_count_active") or 0),
        "intake_count_total": int(intake_sig.get("intake_count_total") or state.get("intake_count_total") or 0),
        "uploaded_file_count": int(intake_sig.get("uploaded_file_count") or state.get("uploaded_file_count") or 0),
        "durable_storage_configured": bool(storage_sig.get("durable_storage_configured", state.get("durable_storage_configured", False))),
        "environment": storage_sig.get("environment") or state.get("environment") or "",
        "git_commit": (state.get("git_commit") or "")[:7],
        "timestamp_utc": state.get("timestamp_utc") or "",
    }
    _organism_cache["payload"] = payload
    _organism_cache["ts"] = now
    return dict(payload)


def reset_organism_cache() -> None:
    """Force a fresh organism summary on the next overview call (used by tests)."""
    _organism_cache["payload"] = None
    _organism_cache["ts"] = 0.0
