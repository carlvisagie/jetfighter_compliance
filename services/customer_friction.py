"""
Customer Friction Elimination Layer v1 — continuation, QR, upload guidance, momentum, telemetry.
All customer-impacting events emit into central memory telemetry (subsystem: customer_friction).
"""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .process import compute_status
from .public_url import get_public_base_url
from .security import (
    CONTINUATION_MAX_AGE_SECONDS,
    make_continuation_token,
    parse_continuation_token,
    parse_intake_token,
)

SUBSYSTEM = "customer_friction"


def _data() -> Path:
    from .config import DATA

    return DATA


def _projects() -> Path:
    from .config import PROJECTS

    return PROJECTS

# Evidence hints — simple language, non-jargon
EVIDENCE_CATALOG: Dict[str, Dict[str, Any]] = {
    "mfa": {
        "title": "Multi-factor authentication (MFA)",
        "plain": "A screenshot showing MFA is turned on for your work accounts.",
        "example_type": "screenshot",
        "example_note": "Settings page showing authenticator app or SMS MFA enabled.",
        "retrieval": {
            "where": ["Microsoft 365 admin center", "Google Workspace security", "Okta dashboard"],
            "steps": [
                "Sign in to your identity provider as an admin.",
                "Open Security / Authentication settings.",
                "Capture a screenshot showing MFA policy or enrollment status.",
                "Upload the image here.",
            ],
            "vendors": ["Microsoft 365", "Google Workspace", "Okta", "Duo"],
        },
    },
    "training": {
        "title": "Security awareness training records",
        "plain": "Proof that staff completed security training (export or certificate).",
        "example_type": "export",
        "example_note": "CSV or PDF export listing employees and completion dates.",
        "retrieval": {
            "where": ["KnowBe4", "Microsoft 365 compliance", "HR learning system"],
            "steps": [
                "Log in to your training platform.",
                "Open Reports or Compliance.",
                "Export completion report as PDF or CSV.",
                "Upload here — any format you already have is fine.",
            ],
            "vendors": ["KnowBe4", "Microsoft 365", "SAP SuccessFactors", "BambooHR"],
        },
    },
    "vendor_policy": {
        "title": "Vendor / supplier security policy",
        "plain": "How you evaluate vendors who touch your data.",
        "example_type": "document",
        "example_note": "Short policy PDF or Word doc describing vendor review.",
        "retrieval": {
            "where": ["Quality manual", "Shared drive / policy folder"],
            "steps": [
                "Locate your supplier or vendor management procedure.",
                "Export or save as PDF.",
                "Upload here.",
            ],
            "vendors": [],
        },
    },
    "ssp_section": {
        "title": "System Security Plan (SSP) excerpt",
        "plain": "A section from your SSP or security overview — we can work with a draft.",
        "example_type": "document",
        "example_note": "Table of contents plus one completed control family is enough to start.",
        "retrieval": {
            "where": ["Compliance folder", "Consultant deliverables", "CMMC workspace"],
            "steps": [
                "Open your latest SSP or security plan draft.",
                "Export the overview or one priority section as PDF.",
                "Upload here.",
            ],
            "vendors": ["C3PAO workspace", "Consultant share folder"],
        },
    },
    "policy_general": {
        "title": "Security or quality policy",
        "plain": "Any policy you already use — handbook, IT policy, quality manual.",
        "example_type": "document",
        "example_note": "PDF or Word; redactions are OK.",
        "retrieval": {
            "where": ["HR handbook", "IT shared drive"],
            "steps": [
                "Pick one policy you already have.",
                "Save as PDF and upload.",
            ],
            "vendors": [],
        },
    },
}

# Filename heuristics for post-upload classification
_CLASSIFY_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(r"mfa|2fa|authenticator|multifactor", re.I), "mfa", "MFA-related file"),
    (re.compile(r"train|awareness|knowbe|phishing", re.I), "training", "Training record"),
    (re.compile(r"vendor|supplier|third.?party", re.I), "vendor_policy", "Vendor policy"),
    (re.compile(r"ssp|system.?security|800-171|nist", re.I), "ssp_section", "SSP / security plan"),
    (re.compile(r"policy|procedure|handbook|manual", re.I), "policy_general", "Policy document"),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(event_type: str, *, project_id: Optional[str] = None, success: bool = True, metadata: Optional[Dict] = None):
    try:
        from services.organism_observability.emit import organism_emit

        entity_id = ""
        if project_id:
            try:
                from services.memory.central_memory import find_entity_id

                entity_id = find_entity_id(project_id=project_id) or ""
            except Exception:
                pass
        organism_emit(
            SUBSYSTEM,
            event_type,
            severity="info" if success else "warning",
            success=success,
            project_id=project_id or "",
            entity_id=entity_id,
            metadata=metadata or {},
            link_timeline=bool(entity_id),
        )
    except Exception:
        pass


def _continuation_meta_path(project_id: str) -> Path:
    return _data() / "projects" / project_id / "communications" / "continuation.json"


def _load_continuation_meta(project_id: str) -> Dict[str, Any]:
    p = _continuation_meta_path(project_id)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_continuation_meta(project_id: str, meta: Dict[str, Any]) -> None:
    pdir = _continuation_meta_path(project_id).parent
    pdir.mkdir(parents=True, exist_ok=True)
    meta["updated_utc"] = _ts()
    _continuation_meta_path(project_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def issue_continuation(project_id: str, email: str, *, force_new: bool = False) -> Dict[str, str]:
    """Create continuation token + URL; persist on project (stable until force_new)."""
    meta = _load_continuation_meta(project_id)
    if (
        not force_new
        and meta.get("continuation_token")
        and meta.get("continuation_url")
        and (not email or meta.get("email") == email)
    ):
        return {
            "continuation_token": meta["continuation_token"],
            "continuation_url": meta["continuation_url"],
        }
    token = make_continuation_token(project_id, email)
    base = get_public_base_url()
    url = f"{base}/ui/continue.html?token={token}"
    meta.update(
        {
            "email": email,
            "continuation_token": token,
            "continuation_url": url,
            "continuation_token_issued_utc": _ts(),
            "expires_seconds": CONTINUATION_MAX_AGE_SECONDS,
        }
    )
    _save_continuation_meta(project_id, meta)
    return {"continuation_token": token, "continuation_url": url}


def get_or_issue_continuation(project_id: str, email: str) -> Dict[str, str]:
    return issue_continuation(project_id, email, force_new=False)


def _project_exists(project_id: str) -> bool:
    return (_data() / "projects" / project_id).is_dir()


def _has_intake(project_id: str) -> bool:
    return (_data() / "projects" / project_id / "communications" / "intake.json").is_file()


def _evidence_files(project_id: str) -> List[Dict[str, str]]:
    ev = _data() / "projects" / project_id / "evidence"
    if not ev.is_dir():
        return []
    out = []
    for f in sorted(ev.iterdir()):
        if f.is_file():
            out.append({"name": f.name, "size": f.stat().st_size})
    return out


def _classify_filename(name: str) -> Tuple[Optional[str], str]:
    for rx, item_id, label in _CLASSIFY_PATTERNS:
        if rx.search(name):
            return item_id, label
    return None, "General document"


def _recommended_missing(project_id: str, recognized: List[str]) -> List[Dict[str, Any]]:
    """Suggest a few missing items — never overwhelm."""
    priority = ["policy_general", "mfa", "training", "vendor_policy", "ssp_section"]
    missing = []
    for item_id in priority:
        if item_id in recognized:
            continue
        cat = EVIDENCE_CATALOG.get(item_id)
        if cat:
            missing.append(
                {
                    "id": item_id,
                    "title": cat["title"],
                    "plain": cat["plain"],
                }
            )
        if len(missing) >= 3:
            break
    return missing


def build_resume_state(project_id: str, email: str = "") -> Dict[str, Any]:
    """Resume snapshot: phase, progress, missing items, next URLs."""
    if not _project_exists(project_id):
        raise ValueError("project_not_found")

    cont = get_or_issue_continuation(project_id, email or _load_continuation_meta(project_id).get("email", ""))
    token = cont["continuation_token"]
    base = get_public_base_url()
    intake_done = _has_intake(project_id)
    files = _evidence_files(project_id)
    recognized_ids: List[str] = []
    recognized_labels: List[str] = []
    for f in files:
        item_id, label = _classify_filename(f["name"])
        if item_id and item_id not in recognized_ids:
            recognized_ids.append(item_id)
            recognized_labels.append(label)

    try:
        st = compute_status(project_id)
        phase = st.get("phase", "ORDER")
        rag = st.get("rag", "green")
        open_steps = [
            s.get("title")
            for s in (st.get("steps") or [])
            if s.get("required") and s.get("status") != "done"
        ][:3]
    except Exception:
        phase, rag, open_steps = "ORDER", "green", []

    if not intake_done:
        next_step = "intake"
        next_url = f"{base}/ui/intake?token={make_intake_token_for(project_id, email)}"
        progress_pct = 25
    elif len(files) < 2:
        next_step = "upload"
        next_url = f"{base}/upload?project_id={project_id}&token={token}"
        progress_pct = min(90, 40 + len(files) * 15)
    else:
        next_step = "upload_more"
        next_url = f"{base}/upload?project_id={project_id}&token={token}"
        progress_pct = min(95, 55 + len(files) * 8)

    missing = _recommended_missing(project_id, recognized_ids)
    momentum_message = _momentum_message(progress_pct, len(files), len(recognized_ids), intake_done)

    return {
        "ok": True,
        "project_id": project_id,
        "email": email,
        "phase": phase,
        "rag": rag,
        "intake_complete": intake_done,
        "upload_count": len(files),
        "uploads": files,
        "recognized": recognized_labels,
        "recognized_ids": recognized_ids,
        "missing_items": missing,
        "open_workflow_steps": open_steps,
        "next_step": next_step,
        "next_url": next_url,
        "continuation_url": cont["continuation_url"],
        "continuation_token": token,
        "intake_url": f"{base}/ui/intake?token={make_intake_token_for(project_id, email)}",
        "upload_url": f"{base}/upload?project_id={project_id}&token={token}",
        "progress_percent": progress_pct,
        "momentum_message": momentum_message,
        "expires_in_days": CONTINUATION_MAX_AGE_SECONDS // 86400,
    }


def make_intake_token_for(project_id: str, email: str) -> str:
    from .security import make_intake_token

    return make_intake_token(project_id, email)


def resolve_continuation(token: str, *, client: str = "unknown") -> Dict[str, Any]:
    try:
        info = parse_continuation_token(token)
    except ValueError as e:
        code = str(e)
        _emit("continuation_abandoned", success=False, metadata={"reason": code, "client": client})
        if code == "continuation_expired":
            return {"ok": False, "error": "expired", "detail": "This link has expired. Contact us for a fresh link."}
        return {"ok": False, "error": "invalid", "detail": "Invalid continuation link."}

    project_id = info["p"]
    email = info.get("e", "")
    _emit("continuation_opened", project_id=project_id, metadata={"client": client})
    meta = _load_continuation_meta(project_id)
    meta["last_opened_utc"] = _ts()
    meta["last_client"] = client
    _save_continuation_meta(project_id, meta)

    state = build_resume_state(project_id, email)
    state["token"] = token
    return state


def record_continuation_event(
    token: str,
    event_type: str,
    *,
    step: str = "",
    client: str = "unknown",
    duration_ms: Optional[int] = None,
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Record continuation_completed, continuation_abandoned, etc."""
    try:
        info = parse_continuation_token(token)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    project_id = info["p"]
    meta = metadata or {}
    meta.update({"step": step, "client": client})
    if duration_ms is not None:
        meta["duration_ms"] = duration_ms

    allowed = {
        "continuation_completed",
        "continuation_abandoned",
        "upload_started",
        "upload_completed",
        "upload_abandoned",
        "example_viewed",
        "retrieval_help_viewed",
        "guidance_viewed",
        "step_abandoned",
    }
    if event_type not in allowed:
        event_type = "continuation_completed"

    success = event_type not in ("continuation_abandoned", "upload_abandoned", "step_abandoned")
    _emit(event_type, project_id=project_id, success=success, metadata=meta)

    if event_type == "continuation_abandoned":
        m = _load_continuation_meta(project_id)
        m["abandoned_utc"] = _ts()
        m["abandoned_step"] = step
        _save_continuation_meta(project_id, m)

    try:
        from services.alerts import raise_alert

        if event_type == "continuation_completed":
            raise_alert(
                "continuation_resumed",
                title="Continuation resumed",
                body=f"Customer returned to project {project_id}.",
                context={"project_id": project_id, "stage": step or "continuation"},
                dedupe_key=f"continuation:{project_id}",
            )
        elif event_type in ("upload_abandoned", "continuation_abandoned", "step_abandoned"):
            raise_alert(
                "upload_abandonment",
                title="Upload / continuation abandoned",
                body=f"Customer left at stage: {step or event_type}.",
                context={"project_id": project_id, "stage": step or event_type},
                dedupe_key=f"abandon:{project_id}:{event_type}",
            )
        elif event_type == "upload_started":
            raise_alert(
                "upload_started",
                title="Upload started",
                body="Customer started an upload on an existing project.",
                context={"project_id": project_id, "stage": step},
                dedupe_key=f"upload_started:{project_id}",
            )
    except Exception:
        pass

    return {"ok": True, "project_id": project_id, "event_type": event_type}


def validate_project_access(project_id: str, token: Optional[str] = None) -> bool:
    """Optional token validates continuation or intake token for project."""
    if not token:
        return _project_exists(project_id)
    try:
        info = parse_continuation_token(token)
        return info.get("p") == project_id
    except ValueError:
        pass
    try:
        info = parse_intake_token(token)
        return info.get("p") == project_id
    except Exception:
        return False


def generate_qr_png(data: str, *, box_size: int = 6) -> bytes:
    import qrcode

    qr = qrcode.QRCode(version=None, box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    try:
        img.save(buf, format="PNG")
    except TypeError:
        # PyPNG backend (no Pillow) — save without format kwarg
        img.save(buf)
    return buf.getvalue()


def qr_url_for_project(project_id: str, email: str, *, page: str = "continue") -> str:
    """Return URL to embed in QR (continuation hub or direct upload)."""
    cont = get_or_issue_continuation(project_id, email)
    if page == "upload":
        return f"{get_public_base_url()}/upload?project_id={project_id}&token={cont['continuation_token']}"
    if page == "intake":
        return f"{get_public_base_url()}/ui/intake?token={make_intake_token_for(project_id, email)}"
    return cont["continuation_url"]


def analyze_uploads(project_id: str) -> Dict[str, Any]:
    files = _evidence_files(project_id)
    classified: List[Dict[str, Any]] = []
    recognized_ids: List[str] = []
    for f in files:
        item_id, label = _classify_filename(f["name"])
        if item_id and item_id not in recognized_ids:
            recognized_ids.append(item_id)
        classified.append({**f, "label": label, "item_id": item_id})

    missing = _recommended_missing(project_id, recognized_ids)
    headline = "We already identified most of what we need." if len(recognized_ids) >= 2 else "Good start — here is what may still help."
    if not files:
        headline = "Upload whatever you already have — we will sort it out."

    return {
        "ok": True,
        "project_id": project_id,
        "headline": headline,
        "subline": "Only a few remaining things may help — upload at your pace.",
        "classified": classified,
        "recognized_count": len(recognized_ids),
        "missing_items": missing,
        "progress_percent": min(95, 35 + len(files) * 12 + len(recognized_ids) * 5),
    }


def get_evidence_example(item_id: str) -> Dict[str, Any]:
    cat = EVIDENCE_CATALOG.get(item_id)
    if not cat:
        return {"ok": False, "error": "not_found"}
    return {
        "ok": True,
        "item_id": item_id,
        "title": cat["title"],
        "plain": cat["plain"],
        "example_type": cat.get("example_type"),
        "example_note": cat.get("example_note"),
    }


def get_retrieval_help(item_id: str) -> Dict[str, Any]:
    cat = EVIDENCE_CATALOG.get(item_id)
    if not cat:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "item_id": item_id, "title": cat["title"], "retrieval": cat.get("retrieval", {})}


def list_evidence_catalog() -> Dict[str, Any]:
    items = [
        {"id": k, "title": v["title"], "plain": v["plain"]}
        for k, v in EVIDENCE_CATALOG.items()
    ]
    return {"ok": True, "items": items}


def _momentum_message(progress_pct: int, upload_count: int, recognized: int, intake_done: bool) -> str:
    if not intake_done:
        return "Good progress — a few intake details and you are on your way."
    if upload_count == 0:
        return "You are set up — upload whatever you already have when ready."
    if recognized >= 2:
        return "We already recognized several items. Only a few remaining things may help."
    return "Nice work — keep adding files at your own pace."


def get_operator_friction_insights(*, days: int = 14) -> Dict[str, Any]:
    """Aggregate customer_friction telemetry for operator cockpit."""
    rows = []
    try:
        from services.memory.telemetry import load_telemetry

        rows = load_telemetry(subsystem=SUBSYSTEM, limit=2000)
    except Exception:
        pass

    cutoff = _utcnow() - __import__("datetime").timedelta(days=days)
    recent = []
    for r in rows:
        ts = r.get("observed_at_utc") or ""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt >= cutoff:
                recent.append(r)
        except Exception:
            recent.append(r)

    def count_event(et: str) -> int:
        return sum(1 for r in recent if r.get("event_type") == et)

    opened = count_event("continuation_opened")
    completed = count_event("continuation_completed")
    abandoned = count_event("continuation_abandoned")
    uploads = count_event("upload_completed")
    examples = count_event("example_viewed")
    retrieval = count_event("retrieval_help_viewed")

    mobile = sum(1 for r in recent if (r.get("metadata") or {}).get("client") == "mobile")
    desktop = sum(1 for r in recent if (r.get("metadata") or {}).get("client") == "desktop")

    # Drop-off by step
    abandon_steps: Dict[str, int] = {}
    for r in recent:
        if r.get("event_type") in ("continuation_abandoned", "step_abandoned", "upload_abandoned"):
            step = (r.get("metadata") or {}).get("step") or "unknown"
            abandon_steps[step] = abandon_steps.get(step, 0) + 1

    example_items: Dict[str, int] = {}
    for r in recent:
        if r.get("event_type") == "example_viewed":
            iid = (r.get("metadata") or {}).get("item_id") or "unknown"
            example_items[iid] = example_items.get(iid, 0) + 1

    recovery_rate = round(100.0 * completed / opened, 1) if opened else None
    mobile_rate = round(100.0 * mobile / (mobile + desktop), 1) if (mobile + desktop) else None

    return {
        "ok": True,
        "window_days": days,
        "continuation_opened": opened,
        "continuation_completed": completed,
        "continuation_abandoned": abandoned,
        "upload_completed": uploads,
        "example_views": examples,
        "retrieval_help_views": retrieval,
        "continuation_recovery_rate_pct": recovery_rate,
        "mobile_events": mobile,
        "desktop_events": desktop,
        "mobile_share_pct": mobile_rate,
        "abandonment_by_step": abandon_steps,
        "top_example_items": sorted(example_items.items(), key=lambda x: -x[1])[:5],
        "top_help_items": _top_retrieval(recent),
    }


def _top_retrieval(rows: List[Dict]) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for r in rows:
        if r.get("event_type") == "retrieval_help_viewed":
            iid = (r.get("metadata") or {}).get("item_id") or "unknown"
            counts[iid] = counts.get(iid, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])[:5]
