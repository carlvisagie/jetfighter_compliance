"""
Customer Friction Elimination Layer v1 — continuation, upload guidance, momentum, telemetry.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import DATA, PROJECTS
from .public_url import get_public_base_url
from .security import make_continuation_token, make_intake_token, parse_continuation_token

CONTINUATION_FILE = "continuation.json"
UPLOAD_SESSION_FILE = "upload_session.json"

# Filename heuristics for post-upload interpretation (organism infers — customer does not classify)
_EVIDENCE_HINTS: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(r"mfa|2fa|authenticator", re.I), "mfa", "Multi-factor authentication"),
    (re.compile(r"train|awareness|knowbe|phish", re.I), "training", "Security awareness training"),
    (re.compile(r"policy|policies|handbook", re.I), "policy", "Security or HR policy"),
    (re.compile(r"ssp|system.security|800-171", re.I), "ssp", "System security plan section"),
    (re.compile(r"pentest|penetration", re.I), "pentest", "Penetration test report"),
    (re.compile(r"soc2|soc\s*2", re.I), "soc2", "SOC 2 report"),
    (re.compile(r"vendor|supplier|subcontract", re.I), "vendor", "Vendor management"),
    (re.compile(r"backup|restore|recovery", re.I), "backup", "Backup and recovery"),
    (re.compile(r"incident|irp", re.I), "incident", "Incident response"),
]

# Common gaps when not detected (friendly ids)
_DEFAULT_GAPS = [
    {
        "id": "mfa",
        "title": "MFA enabled screenshot",
        "why": "Shows access controls for accounts handling sensitive data.",
    },
    {
        "id": "training",
        "title": "Security awareness training records",
        "why": "Demonstrates people-focused controls.",
    },
    {
        "id": "policy",
        "title": "Written security policy",
        "why": "Foundation document auditors expect to see.",
    },
]

EVIDENCE_EXAMPLES: Dict[str, Dict[str, Any]] = {
    "mfa": {
        "title": "MFA screenshot example",
        "summary": "A screenshot of your admin console showing MFA enabled for users.",
        "example_type": "screenshot",
        "what_is_this": "Proof that accounts use a second factor (app, SMS, or hardware key).",
    },
    "training": {
        "title": "Training export example",
        "summary": "CSV or PDF export from your training platform with completion dates.",
        "example_type": "document",
        "what_is_this": "Shows your team completed security awareness training.",
    },
    "policy": {
        "title": "Policy document example",
        "summary": "PDF of your information security or acceptable-use policy (signed or dated).",
        "example_type": "document",
        "what_is_this": "Written rules for how your organization protects data.",
    },
    "ssp": {
        "title": "SSP section sample",
        "summary": "One section of a System Security Plan describing how a control is implemented.",
        "example_type": "document",
        "what_is_this": "Narrative evidence for CMMC/NIST-style assessments.",
    },
    "vendor": {
        "title": "Vendor policy example",
        "summary": "Policy or procedure describing how you review third-party vendors.",
        "example_type": "document",
        "what_is_this": "Shows supply-chain risk is managed.",
    },
}

RETRIEVAL_HELP: Dict[str, Dict[str, Any]] = {
    "mfa": {
        "where_usually": "Microsoft 365 Admin, Google Workspace Admin, or your IdP dashboard.",
        "sources": ["Microsoft 365", "Google Workspace", "Okta", "Duo"],
        "quick_start": [
            "Sign in to your admin portal.",
            "Open Users or Security settings.",
            "Find MFA / 2FA status page.",
            "Take a screenshot showing MFA enabled.",
            "Upload the screenshot here.",
        ],
    },
    "training": {
        "where_usually": "KnowBe4, Microsoft 365 compliance reports, or HR/LMS exports.",
        "sources": ["KnowBe4", "Microsoft 365", "HR systems"],
        "quick_start": [
            "Log in to your training platform.",
            "Open Reports or Compliance.",
            "Export completion report (PDF or CSV).",
            "Upload the export here.",
        ],
    },
    "policy": {
        "where_usually": "SharePoint, Google Drive, or policy management tool.",
        "sources": ["Internal wiki", "SharePoint", "Compliance folder"],
        "quick_start": [
            "Locate your latest security policy PDF.",
            "Confirm it is dated or approved.",
            "Upload the PDF here.",
        ],
    },
    "ssp": {
        "where_usually": "CMMC consultant folder, GRC tool, or shared compliance drive.",
        "sources": ["GRC platform", "Consultant deliverables"],
        "quick_start": [
            "Open your SSP working document.",
            "Export one completed control section as PDF.",
            "Upload here — we will organize it.",
        ],
    },
    "vendor": {
        "where_usually": "Vendor management spreadsheet or procurement policy folder.",
        "sources": ["Procurement", "Legal", "Security team"],
        "quick_start": [
            "Find vendor review procedure or template.",
            "Export or save as PDF.",
            "Upload here.",
        ],
    },
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _project_dir(project_id: str) -> Path:
    return DATA / "projects" / project_id


def _communications_dir(project_id: str) -> Path:
    d = _project_dir(project_id) / "communications"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _has_intake(project_id: str) -> bool:
    return (_communications_dir(project_id) / "intake.json").is_file()


def _workflow_phase(project_id: str) -> str:
    wf = DATA / "process" / f"{project_id}.json"
    if not wf.is_file():
        return "INTAKE"
    try:
        return json.loads(wf.read_text(encoding="utf-8")).get("phase", "INTAKE")
    except Exception:
        return "INTAKE"


def _list_evidence_files(project_id: str) -> List[Dict[str, Any]]:
    ev = _project_dir(project_id) / "evidence"
    if not ev.is_dir():
        return []
    out = []
    for f in sorted(ev.iterdir()):
        if f.is_file():
            out.append({"name": f.name, "size": f.stat().st_size})
    return out


def _classify_filename(name: str) -> Optional[str]:
    for rx, key, _ in _EVIDENCE_HINTS:
        if rx.search(name):
            return key
    return None


def _emit(event_type: str, *, project_id: str = "", success: bool = True, metadata: Optional[Dict] = None):
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            "customer_friction",
            event_type,
            project_id=project_id,
            success=success,
            metadata=metadata or {},
        )
    except Exception:
        pass


def _learn(signal: str, conversion: str, *, success: bool = True, **meta):
    try:
        from services.memory.learning import record_learning_signal

        record_learning_signal(signal, conversion, success=success, **meta)
    except Exception:
        pass


def ensure_continuation_record(project_id: str, email: str) -> Dict[str, Any]:
    """Create or refresh continuation token + URL on disk."""
    token = make_continuation_token(project_id, email)
    base = get_public_base_url()
    continuation_url = f"{base}/ui/continue.html?token={token}"
    intake_url = f"{base}/ui/intake.html?token={token}"
    upload_url = f"{base}/upload?project_id={project_id}&token={token}"
    rec = {
        "project_id": project_id,
        "email": email,
        "continuation_token": token,
        "continuation_url": continuation_url,
        "intake_url": intake_url,
        "upload_url": upload_url,
        "updated_utc": _ts(),
        "expires_note": "Link remains valid for 90 days; request a new welcome email if expired.",
    }
    path = _communications_dir(project_id) / CONTINUATION_FILE
    if path.is_file():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            rec["created_utc"] = old.get("created_utc", _ts())
            rec["open_count"] = old.get("open_count", 0)
        except Exception:
            rec["created_utc"] = _ts()
    else:
        rec["created_utc"] = _ts()
        rec["open_count"] = 0
    path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def build_continuation_bundle(project_id: str, email: str) -> Dict[str, str]:
    rec = ensure_continuation_record(project_id, email)
    return {
        "continuation_token": rec["continuation_token"],
        "continuation_url": rec["continuation_url"],
        "intake_url": rec["intake_url"],
        "upload_url": rec["upload_url"],
    }


def resolve_continuation(token: str, *, client: str = "unknown") -> Dict[str, Any]:
    """Magic link resolve — no password."""
    info = parse_continuation_token(token)
    project_id = info["p"]
    email = info.get("e", "")
    pdir = _project_dir(project_id)
    if not pdir.is_dir():
        raise ValueError("project_not_found")

    rec_path = _communications_dir(project_id) / CONTINUATION_FILE
    if rec_path.is_file():
        try:
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
            rec["open_count"] = int(rec.get("open_count", 0)) + 1
            rec["last_opened_utc"] = _ts()
            rec_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        except Exception:
            pass
    else:
        ensure_continuation_record(project_id, email)

    intake_done = _has_intake(project_id)
    uploads = _list_evidence_files(project_id)
    phase = _workflow_phase(project_id)
    intake_tok = make_intake_token(project_id, email)
    base = get_public_base_url()
    if not intake_done:
        next_step = "intake"
        primary_url = f"{base}/ui/intake.html?token={intake_tok}"
    elif len(uploads) < 1:
        next_step = "upload"
        primary_url = f"{base}/upload?project_id={project_id}&token={intake_tok}"
    else:
        next_step = "upload_more"
        primary_url = f"{base}/upload?project_id={project_id}&token={intake_tok}"

    state = get_resume_state(project_id)
    _emit(
        "continuation_opened",
        project_id=project_id,
        metadata={"next_step": next_step, "client": client, "upload_count": len(uploads)},
    )
    _learn(f"continuation:{next_step}", "inquiry_to_intake", success=True)

    qr_url = f"{base}/api/customer/qr.svg?url={primary_url}"

    return {
        "ok": True,
        "project_id": project_id,
        "email": email,
        "next_step": next_step,
        "workflow_phase": phase,
        "intake_completed": intake_done,
        "upload_count": len(uploads),
        "primary_url": primary_url,
        "intake_url": f"{base}/ui/intake.html?token={intake_tok}",
        "upload_url": f"{base}/upload?project_id={project_id}&token={intake_tok}",
        "continuation_url": f"{base}/ui/continue.html?token={token}",
        "qr_url": qr_url,
        "resume": state,
        "momentum": momentum_message(project_id, intake_done, len(uploads)),
    }


def get_resume_state(project_id: str) -> Dict[str, Any]:
    uploads = _list_evidence_files(project_id)
    intake_done = _has_intake(project_id)
    identified = []
    for u in uploads:
        cat = _classify_filename(u["name"])
        if cat:
            identified.append({"file": u["name"], "category": cat})
    guidance = analyze_uploads(project_id)
    return {
        "intake_completed": intake_done,
        "uploads": uploads,
        "identified": identified,
        "missing_items": guidance.get("likely_missing", []),
        "progress_percent": guidance.get("progress_percent", 0),
    }


def momentum_message(project_id: str, intake_done: bool, upload_count: int) -> Dict[str, str]:
    if not intake_done:
        return {
            "headline": "Good start — let's finish your intake",
            "subline": "A few quick details, then you can upload whatever you already have.",
            "tone": "encouraging",
        }
    if upload_count == 0:
        return {
            "headline": "You're on track",
            "subline": "Upload whatever you already have — no need to organize it first.",
            "tone": "encouraging",
        }
    if upload_count < 3:
        return {
            "headline": "Good progress",
            "subline": "We already recognized several items from your uploads.",
            "tone": "positive",
        }
    return {
        "headline": "Strong momentum",
        "subline": "Only a few remaining things may help — upload more anytime.",
        "tone": "positive",
    }


def analyze_uploads(project_id: str) -> Dict[str, Any]:
    uploads = _list_evidence_files(project_id)
    detected: Dict[str, str] = {}
    for u in uploads:
        cat = _classify_filename(u["name"])
        if cat:
            detected[cat] = u["name"]

    likely_missing = []
    for gap in _DEFAULT_GAPS:
        if gap["id"] not in detected:
            likely_missing.append(
                {
                    **gap,
                    "example": EVIDENCE_EXAMPLES.get(gap["id"]),
                    "retrieval": RETRIEVAL_HELP.get(gap["id"]),
                }
            )
    # Cap overwhelm — max 4 suggestions
    likely_missing = likely_missing[:4]

    total_hints = len(_DEFAULT_GAPS)
    progress = min(100, int((len(detected) / max(total_hints, 1)) * 100))
    if len(uploads) >= 5:
        progress = max(progress, 70)

    return {
        "ok": True,
        "project_id": project_id,
        "upload_count": len(uploads),
        "recognized": [{"category": k, "file": v} for k, v in detected.items()],
        "likely_missing": likely_missing,
        "progress_percent": progress,
        "summary": "We already identified most of what we need."
        if len(detected) >= 2
        else "Upload whatever you have — we will sort it out.",
    }


def record_continuation_event(
    token: str,
    event: str,
    *,
    step: str = "",
    client: str = "unknown",
    duration_ms: Optional[int] = None,
) -> Dict[str, Any]:
    info = parse_continuation_token(token)
    project_id = info["p"]
    allowed = {"continuation_opened", "continuation_completed", "continuation_abandoned"}
    if event not in allowed:
        event = f"continuation_{event}" if not event.startswith("continuation_") else event
    _emit(
        event if event in allowed else "continuation_abandoned",
        project_id=project_id,
        success=event != "continuation_abandoned",
        metadata={"step": step, "client": client, "duration_ms": duration_ms},
    )
    if event == "continuation_completed":
        _learn("onboarding:completed", "intake_to_evidence", success=True)
    elif event == "continuation_abandoned":
        _learn(f"dropoff:{step or 'unknown'}", "inquiry_to_intake", success=False)
    return {"ok": True, "project_id": project_id, "event": event}


def save_upload_session(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    path = _communications_dir(project_id) / UPLOAD_SESSION_FILE
    data = {"updated_utc": _ts(), **payload}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _emit("upload_session_saved", project_id=project_id, metadata={"files": payload.get("files", [])})
    return {"ok": True, "session": data}


def load_upload_session(project_id: str) -> Dict[str, Any]:
    path = _communications_dir(project_id) / UPLOAD_SESSION_FILE
    if not path.is_file():
        return {"ok": True, "session": None}
    try:
        return {"ok": True, "session": json.loads(path.read_text(encoding="utf-8"))}
    except Exception:
        return {"ok": True, "session": None}


def get_evidence_example(item_id: str) -> Dict[str, Any]:
    ex = EVIDENCE_EXAMPLES.get(item_id)
    if not ex:
        return {"ok": False, "detail": "unknown_item"}
    return {"ok": True, "item_id": item_id, **ex, "retrieval": RETRIEVAL_HELP.get(item_id)}


def get_retrieval_help(item_id: str) -> Dict[str, Any]:
    h = RETRIEVAL_HELP.get(item_id)
    if not h:
        return {"ok": False, "detail": "unknown_item"}
    _emit("retrieval_help_viewed", metadata={"item_id": item_id})
    _learn(f"help:{item_id}", "intake_to_evidence", success=True)
    return {"ok": True, "item_id": item_id, **h}


def record_example_viewed(item_id: str, project_id: str = "") -> None:
    _emit("example_viewed", project_id=project_id, metadata={"item_id": item_id})
    _learn(f"example:{item_id}", "intake_to_evidence", success=True)


def friction_insights_for_operator(limit: int = 200) -> Dict[str, Any]:
    """Aggregate telemetry for operator cockpit panels."""
    from services.memory.telemetry import load_telemetry

    rows = load_telemetry(subsystem="customer_friction", limit=limit)
    opened = completed = abandoned = 0
    examples = retrieval = 0
    mobile = desktop = 0
    dropoffs: Dict[str, int] = {}
    help_items: Dict[str, int] = {}

    for r in rows:
        et = r.get("event_type", "")
        meta = r.get("metadata") or {}
        if et == "continuation_opened":
            opened += 1
        elif et == "continuation_completed":
            completed += 1
        elif et == "continuation_abandoned":
            abandoned += 1
            step = meta.get("step") or "unknown"
            dropoffs[step] = dropoffs.get(step, 0) + 1
        elif et == "example_viewed":
            examples += 1
            iid = meta.get("item_id", "unknown")
            help_items[iid] = help_items.get(iid, 0) + 1
        elif et == "retrieval_help_viewed":
            retrieval += 1
            iid = meta.get("item_id", "unknown")
            help_items[iid] = help_items.get(iid, 0) + 1
        client = meta.get("client", "")
        if client == "mobile":
            mobile += 1
        elif client == "desktop":
            desktop += 1

    completion_rate = round(completed / opened, 2) if opened else None
    recovery_rate = round(opened / max(opened + abandoned, 1), 2)

    top_help = sorted(help_items.items(), key=lambda x: -x[1])[:8]
    top_dropoffs = sorted(dropoffs.items(), key=lambda x: -x[1])[:8]

    return {
        "ok": True,
        "continuation": {
            "opened": opened,
            "completed": completed,
            "abandoned": abandoned,
            "completion_rate": completion_rate,
            "recovery_rate": recovery_rate,
        },
        "mobile_vs_desktop": {"mobile": mobile, "desktop": desktop},
        "example_views": examples,
        "retrieval_help_views": retrieval,
        "top_requested_help": [{"item_id": k, "count": v} for k, v in top_help],
        "onboarding_dropoffs": [{"step": k, "count": v} for k, v in top_dropoffs],
        "confusing_evidence_requests": [
            {"item_id": k, "count": v} for k, v in top_help if v >= 2
        ],
    }


def record_upload_completed(project_id: str, filename: str) -> Dict[str, Any]:
    _emit("upload_completed", project_id=project_id, metadata={"filename": filename})
    return analyze_uploads(project_id)


def make_qr_svg(url: str) -> str:
    import qrcode
    import qrcode.image.svg

    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(image_factory=factory, box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image()
    raw = img.to_string()
    return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
