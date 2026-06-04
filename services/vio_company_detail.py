"""VIO 2.0 — per-company composite detail.

Aggregates everything an operator needs to understand a single company,
so they never have to leave VIO and dig into GitHub, Render, logs, or
the file system:

  - uploaded documents (with view/download URLs + lifecycle state)
  - generated documents (forward-compatible; empty until generation lands)
  - missing documents (gaps from evidence intelligence)
  - evidence summary (counts + extracted profile)
  - findings (per-company red/amber signals derived locally)

The endpoint is intentionally read-only and operator-protected.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _safe(call, default):
    try:
        return call()
    except Exception:
        return default


def _ts_age_hours(utc_str: str) -> float:
    try:
        dt = datetime.fromisoformat((utc_str or "").replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return 0.0


def _initials(name: str) -> str:
    parts = (name or "?").split()
    return "".join(p[0].upper() for p in parts[:2]) or "?"


# ── Finding derivation ────────────────────────────────────────────────────────
def _derive_findings(
    rec: Dict[str, Any],
    files_payload: Dict[str, Any],
    ei: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build per-company findings from intake + files + EI signals.

    Each finding: {severity: red|amber|info, code, message, hint?}
    """
    findings: List[Dict[str, Any]] = []

    documents = list(files_payload.get("documents") or [])

    # 1. Files recorded but missing from disk (chain of custody break)
    missing_on_disk = [
        d.get("stored_name") for d in documents
        if d.get("access_error") or d.get("status") in ("missing", "broken")
    ]
    if missing_on_disk:
        findings.append({
            "severity": "red",
            "code": "files_missing_on_disk",
            "message": (
                f"{len(missing_on_disk)} file(s) recorded for this intake are "
                f"missing on durable storage"
            ),
            "hint": "Check Render disk mount and recent deploy history.",
        })

    # 2. Disk-only unindexed files (uploaded but never registered)
    unindexed = [d for d in documents if d.get("status") == "on_disk_unindexed"]
    if unindexed:
        findings.append({
            "severity": "amber",
            "code": "files_unindexed",
            "message": f"{len(unindexed)} file(s) found on disk without intake metadata",
            "hint": "Customer upload may have completed mid-failure. Re-classify.",
        })

    # 3. Extraction failures
    failures = int(ei.get("extraction_failures") or 0)
    if failures:
        findings.append({
            "severity": "amber",
            "code": "extraction_failures",
            "message": f"{failures} extraction failure(s) — some documents could not be read",
            "hint": "Ask customer to provide PDF/text exports if scans/images failed.",
        })

    # 4. Pending analysis (large/unsupported)
    pending = int(ei.get("pending_analysis") or 0)
    if pending:
        findings.append({
            "severity": "info",
            "code": "pending_analysis",
            "message": f"{pending} file(s) pending analysis (large or unsupported format)",
        })

    # 5. Confirmation needed
    confirm = ei.get("confirmation_needed") or []
    if confirm:
        findings.append({
            "severity": "info",
            "code": "confirmation_needed",
            "message": f"{len(confirm)} extracted field(s) need customer confirmation",
            "hint": "Send the customer a continuation link.",
        })

    # 6. Compliance gaps (already surfaced separately, but mirror as finding)
    gaps = ei.get("gaps") or []
    high = [g for g in gaps if (g.get("priority") if isinstance(g, dict) else getattr(g, "priority", "")) == "high"]
    if high:
        findings.append({
            "severity": "amber",
            "code": "high_priority_gaps",
            "message": f"{len(high)} high-priority evidence gap(s) detected",
        })

    # 7. Stuck intake (no uploads, no review action, > 48h)
    age = _ts_age_hours(rec.get("created_at_utc") or rec.get("created_utc") or "")
    review_status = str(rec.get("review_status") or "")
    file_count = int(files_payload.get("file_count") or 0)
    if age > 48 and file_count == 0 and review_status == "pending_review":
        findings.append({
            "severity": "red",
            "code": "stuck_intake_no_upload",
            "message": f"Intake is {int(age)}h old with zero files and no operator action",
            "hint": "Contact customer or archive.",
        })

    # 8. Payment requested but no response
    payment = rec.get("payment") or {}
    if review_status in ("approved", "payment_sent") and not payment.get("paid"):
        sent_age = _ts_age_hours(payment.get("link_sent_utc") or "")
        if sent_age > 72:
            findings.append({
                "severity": "amber",
                "code": "payment_link_stale",
                "message": f"Payment link sent {int(sent_age)}h ago — no payment received",
                "hint": "Resend link or follow up.",
            })

    return findings


def _bottleneck(findings: List[Dict[str, Any]], review_status: str) -> Optional[str]:
    """Pick the single most urgent thing for the operator to address."""
    order = ("red", "amber", "info")
    for sev in order:
        for f in findings:
            if f.get("severity") == sev:
                return f.get("message")
    if review_status == "pending_review":
        return "Awaiting operator review"
    if review_status in ("approved", "payment_sent"):
        return "Awaiting customer payment"
    return None


# ── Generated documents (placeholder) ─────────────────────────────────────────
def _generated_documents(project_id: str) -> List[Dict[str, Any]]:
    """Scan project artifact folders for documents the platform has produced.

    Currently the platform does not auto-generate compliance paperwork, so this
    returns []. Forward-compatible: when generation lands, files dropped into
    data/projects/<id>/generated/ will appear automatically.
    """
    if not project_id:
        return []
    try:
        from services.evidence_intelligence import DATA  # type: ignore
    except Exception:
        return []
    gen_dir = DATA / "projects" / project_id / "generated"
    if not gen_dir.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for p in sorted(gen_dir.iterdir()):
        if p.is_file():
            try:
                stat = p.stat()
                out.append({
                    "name": p.name,
                    "size_bytes": stat.st_size,
                    "created_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "kind": "generated",
                })
            except Exception:
                continue
    return out


# ── Missing documents derived from gaps ────────────────────────────────────────
def _missing_documents(ei: Dict[str, Any]) -> List[Dict[str, Any]]:
    gaps = ei.get("gaps") or []
    out: List[Dict[str, Any]] = []
    for g in gaps:
        if isinstance(g, dict):
            out.append({
                "gap_id": g.get("gap_id") or g.get("id"),
                "label": g.get("label") or g.get("gap_id") or "Unknown gap",
                "priority": g.get("priority") or "medium",
                "explanation": g.get("explanation") or g.get("description") or "",
                "example_url": g.get("example_url") or "",
                "retrieval_help_url": g.get("retrieval_help_url") or "",
            })
    return out


# ── Document presentation ─────────────────────────────────────────────────────
def _present_uploaded_documents(documents: List[Dict[str, Any]], ei: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Merge intake doc list with EI classifications so each row has a doc type.

    Source schema (from services.intake.operator_files._document_row):
      stored_filename, original_filename, extension, media_type, size_bytes,
      sha256, status, view_url, download_url, accessible, access_error
    """
    class_by_file: Dict[str, Dict[str, Any]] = {}
    for c in ei.get("document_types") or []:
        if isinstance(c, dict):
            fname = c.get("file") or c.get("filename") or ""
            if fname:
                class_by_file[fname] = c

    presented: List[Dict[str, Any]] = []
    for d in documents:
        stored = d.get("stored_filename") or d.get("stored_name") or ""
        original = d.get("original_filename") or d.get("original_name") or stored
        cls = class_by_file.get(stored) or {}
        presented.append({
            "stored_name": stored,
            "original_name": original,
            "extension": d.get("extension") or "",
            "media_type": d.get("media_type") or "",
            "size_bytes": d.get("size_bytes"),
            "size_human": d.get("size_human") or "",
            "sha256": d.get("sha256"),
            "sha256_short": d.get("sha256_short"),
            "status": d.get("status") or "unknown",
            "accessible": d.get("accessible", True),
            "access_error": d.get("access_error"),
            "view_url": d.get("view_url") or "",
            "download_url": d.get("download_url") or "",
            "preview_url": d.get("preview_url") or d.get("view_url") or "",
            "previewable": bool(d.get("previewable")),
            "preview_mode": d.get("preview_mode") or "none",
            "document_type": cls.get("type") or cls.get("document_type") or "",
            "classification_confidence": cls.get("confidence"),
        })
    return presented


# ── Main entry ────────────────────────────────────────────────────────────────
def build_company_detail(intake_id: str) -> Dict[str, Any]:
    """Build the full operator awareness payload for one company."""
    from services.intake.storage import load_intake_record, intake_dir

    iid = intake_id.strip()

    # load_intake_record() recovers a stub for unknown IDs, so verify the
    # intake actually exists on disk before treating it as real.
    try:
        idir = intake_dir(iid)
    except Exception:
        idir = None
    if idir is None or not idir.is_dir():
        return {"ok": False, "error": "intake not found", "intake_id": iid}

    from services.intake.operator_files import list_intake_files_for_operator

    try:
        rec = load_intake_record(iid, persist_recovery=False)
    except Exception as exc:
        return {"ok": False, "error": f"intake not loadable: {exc}", "intake_id": iid}

    company_name = rec.get("company") or rec.get("company_name") or "Unknown"
    contact_email = rec.get("email") or rec.get("contact_email") or ""
    project_id = rec.get("project_id") or ""
    review_status = str(rec.get("review_status") or "")

    files_payload = _safe(lambda: list_intake_files_for_operator(iid), {"documents": [], "file_count": 0})

    ei: Dict[str, Any] = {}
    if project_id:
        try:
            from services.evidence_intelligence import get_operator_evidence_intelligence
            ei = get_operator_evidence_intelligence(project_id) or {}
        except Exception:
            ei = {}

    documents = _present_uploaded_documents(files_payload.get("documents") or [], ei)
    generated = _generated_documents(project_id)
    missing = _missing_documents(ei)
    findings = _derive_findings(rec, files_payload, ei)
    bottleneck = _bottleneck(findings, review_status)

    # ── Classification / category (anchored at the `classification` stage) ──
    classification = {
        "primary_category": str(rec.get("primary_category") or "").strip(),
        "secondary_category": str(rec.get("secondary_category") or "").strip(),
        "scope_label": str(rec.get("scope_label") or "").strip(),
    }

    # ── Items the customer must confirm (anchored at evidence_mapping) ──
    confirmation_needed: List[Dict[str, Any]] = []
    for c in (ei.get("confirmation_needed") or []):
        if isinstance(c, dict):
            confirmation_needed.append({
                "field": c.get("field") or "",
                "value": c.get("value") or "",
                "status": c.get("status") or "",
                "source_file": c.get("source_file") or c.get("file") or "",
            })

    return {
        "ok": True,
        "intake_id": iid,
        "project_id": project_id,
        "company_name": company_name,
        "initials": _initials(company_name),
        "contact_email": contact_email,
        "review_status": review_status,
        "created_utc": rec.get("created_at_utc") or rec.get("created_utc") or "",
        "age_hours": round(_ts_age_hours(rec.get("created_at_utc") or rec.get("created_utc") or ""), 1),
        # ── Intake-side context (used by Level 2 intake branch) ──────────
        "intake_context": {
            "context": str(rec.get("context") or "").strip(),
            "phone": str(rec.get("phone") or "").strip(),
            "deadline": str(rec.get("deadline") or "").strip(),
            "urgent": bool(rec.get("urgent") or False),
            "expected_file_count": rec.get("expected_file_count"),
            "source_ip": rec.get("source_ip") or "",
            "user_agent": (rec.get("user_agent") or "")[:120],
        },
        # ── Classification (used by Level 2 classification branch) ──────
        "classification": classification,
        "uploaded_documents": documents,
        "generated_documents": generated,
        "missing_documents": missing,
        # ── Customer-confirmation items (used by Level 2 evidence branch) ──
        "confirmation_needed": confirmation_needed,
        "evidence": {
            "files_uploaded": int(ei.get("files_uploaded") or files_payload.get("file_count") or 0),
            "files_analyzed": int(ei.get("files_analyzed") or 0),
            "entity_count": int(ei.get("entity_count") or 0),
            "missing_item_count": int(ei.get("missing_item_count") or 0),
            "extraction_failures": int(ei.get("extraction_failures") or 0),
            "pending_analysis": int(ei.get("pending_analysis") or 0),
            "confidence_summary": ei.get("confidence_summary") or {},
            "profile": ei.get("profile") or {},
            "available": bool(ei),
        },
        "findings": findings,
        "bottleneck": bottleneck,
        "next_actions": list(ei.get("next_actions") or []),
        "payment": rec.get("payment") or {},
    }
