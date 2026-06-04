"""Evidence Intelligence Layer v1 — rule-based upload analysis."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

from ..config import DATA
from ..public_url import get_public_base_url
from . import storage, telemetry
from .classification import classify_document
from .confidence import summarize_confidence
from .domains import detect_compliance_domain
from .entities import extract_entities
from .extraction import extract_from_file, redact_secrets
from .gaps import detect_gaps
from .profile import needs_confirmation, profile_to_customer_identified, update_profile
from .schemas import ProcessingResult

ConfirmAction = Literal["confirmed", "rejected", "unsure"]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _enrich_gaps(gaps: List[Any]) -> List[Dict[str, Any]]:
    base = get_public_base_url().rstrip("/")
    out: List[Dict[str, Any]] = []
    for g in gaps:
        d = g.model_dump() if hasattr(g, "model_dump") else dict(g)
        key = d.get("example_item_id") or ""
        if key:
            d["example_url"] = f"{base}/api/customer/evidence/example/{key}"
            d["retrieval_help_url"] = f"{base}/api/customer/evidence/retrieval/{key}"
        out.append(d)
    return out


# Internal sidecars and orchestration metadata that must NEVER be counted
# as customer evidence. Production intake FB-1dfab13c120b (2026-06-04)
# surfaced classifications + entities derived from these files because the
# intake.py loop used to ``rglob("*")`` the whole intake directory. The
# loop is now scoped to ``uploads/``, but we keep this read-side filter to
# clean up data already on disk and to defend against future regressions.
_EI_INTERNAL_FILENAMES = frozenset({
    "intake.json",
    "classification.json",
    "profile.json",
    "extractions.jsonl",
    "classifications.jsonl",
    "entities.jsonl",
    "gaps.json",
    "review_queue.jsonl",
})


def _is_real_customer_upload(name: str) -> bool:
    """True only for filenames that came from a customer upload."""
    if not name:
        return False
    n = str(name).strip()
    if n in _EI_INTERNAL_FILENAMES:
        return False
    if n.endswith(".durability.json"):
        return False
    return True


def _scrub_profile_pollution(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Remove rows / entities derived from internal metadata files.

    Earlier production EI runs polluted ``profile.json`` itself with
    rows whose source filename is ``intake.json``, ``classification.json``,
    or ``*.durability.json``. The downstream domain detector reads
    those inventory rows and was picking CMMC for a life-coaching
    company because ``classification.json`` got mis-classified as
    "ssp". Scrubbing on read keeps already-on-disk pollution out of
    the awareness layer without needing a destructive backfill.
    """
    if not isinstance(profile, dict):
        return profile
    inv = profile.get("document_inventory")
    if isinstance(inv, list):
        profile["document_inventory"] = [
            row for row in inv
            if _is_real_customer_upload(str((row or {}).get("file") or ""))
        ]
    for bucket in (
        "company_name_candidates",
        "emails",
        "phones",
        "addresses",
        "domains",
        "websites",
        "people",
        "vendors",
        "technologies",
        "cloud_providers",
        "identity_providers",
        "compliance_references",
    ):
        items = profile.get(bucket)
        if not isinstance(items, list):
            continue
        cleaned = []
        for item in items:
            if not isinstance(item, dict):
                continue
            src   = str(item.get("source_file") or "")
            value = str(item.get("value") or "")
            if src and not _is_real_customer_upload(src):
                continue
            if value.endswith(".durability.json"):
                continue
            cleaned.append(item)
        profile[bucket] = cleaned
    return profile


def _already_processed(project_id: str, sha256_val: str, artifact_id: str) -> bool:
    """Return True if this exact artifact was already extracted successfully."""
    if not sha256_val and not artifact_id:
        return False
    for row in storage.load_jsonl(project_id, "extractions.jsonl", limit=500):
        if sha256_val and row.get("sha256") == sha256_val and row.get("status") == "completed":
            return True
        if artifact_id and row.get("artifact_id") == artifact_id and row.get("status") == "completed":
            return True
    return False


def process_evidence_upload(
    project_id: str,
    file_path: Path,
    *,
    artifact_id: str = "",
    sha256: str = "",
    owner: str = "",
) -> ProcessingResult:
    """Analyze one uploaded file; never raises to caller."""
    name = file_path.name
    actual_sha256 = sha256 or _sha256_file(file_path)

    # Skip reprocessing identical artifacts (idempotent on duplicate uploads)
    if _already_processed(project_id, actual_sha256, artifact_id):
        result = ProcessingResult(project_id=project_id, source_file=name)
        result.status = "completed"
        result.message = "We already organized this file."
        telemetry.emit(
            "evidence_extraction_completed",
            project_id=project_id,
            metadata={"file": name, "status": "duplicate_skipped"},
        )
        return result

    result = ProcessingResult(project_id=project_id, source_file=name)
    telemetry.emit("evidence_extraction_started", project_id=project_id, metadata={"file": name})

    try:
        extraction = extract_from_file(file_path)
        result.extraction = extraction

        if extraction.ocr_applied:
            telemetry.emit(
                "evidence_ocr_applied",
                project_id=project_id,
                metadata={
                    "file":             name,
                    "ocr_text_length":  extraction.ocr_text_length,
                    "extraction_method": extraction.extraction_method,
                },
            )
        elif extraction.ocr_status in (
            "ocr_module_unavailable",
            "ocr_binary_unavailable",
            "ocr_failed",
            "ocr_empty",
        ):
            telemetry.emit(
                "evidence_ocr_skipped",
                project_id=project_id,
                metadata={"file": name, "reason": extraction.ocr_status},
            )

        if extraction.pending_analysis and not extraction.text_preview:
            result.status = "pending_analysis"
            result.message = "We received your files. We are organizing them now."
            rec = extraction.model_dump()
            rec.update({"sha256": actual_sha256, "artifact_id": artifact_id, "status": "pending_analysis"})
            storage.append_jsonl(project_id, "extractions.jsonl", rec)
            telemetry.emit(
                "evidence_extraction_completed",
                project_id=project_id,
                metadata={"file": name, "status": "pending"},
            )
            try:
                from services.memory.organism_integration import safe_write_after_evidence_intelligence

                safe_write_after_evidence_intelligence(
                    project_id,
                    filename=name,
                    artifact_id=artifact_id,
                    sha256=actual_sha256,
                    status="pending_analysis",
                )
            except Exception:
                pass
            return result

        text = extraction.text_preview or ""
        classification = classify_document(text, name)
        entities = extract_entities(text, name, filename=name)
        result.classification = classification
        result.entities_extracted = len(entities)

        profile = storage.load_profile(project_id)
        profile["project_id"] = project_id
        update_profile(profile, entities, classification)
        # Domain detection — operator and customer payloads both surface
        # this so the recommendations are framework-relevant (DOT vs
        # CMMC vs EU DPP vs HIPAA), not a one-size-fits-all CMMC pack.
        domain_result = detect_compliance_domain(
            profile,
            texts=[text],
            classifications=[classification.model_dump()],
        )
        profile["primary_domain"]    = domain_result.domain
        profile["domain_confidence"] = domain_result.confidence
        profile["domain_signals"]    = {
            k: list(v) for k, v in (domain_result.signals or {}).items()
        }
        if domain_result.domain and domain_result.domain != "general":
            telemetry.emit(
                "compliance_domain_detected",
                project_id=project_id,
                metadata={
                    "domain":     domain_result.domain,
                    "confidence": domain_result.confidence,
                    "runner_up":  domain_result.runner_up,
                },
            )
        gaps = detect_gaps(profile, domain=domain_result.domain or None)
        storage.write_profile(project_id, profile)
        storage.write_gaps(project_id, [g.model_dump() for g in gaps])
        extraction_rec = extraction.model_dump()
        extraction_rec.update({"sha256": actual_sha256, "artifact_id": artifact_id, "status": "completed"})
        storage.append_jsonl(project_id, "extractions.jsonl", extraction_rec)
        storage.append_jsonl(project_id, "classifications.jsonl", classification.model_dump())
        for ent in entities:
            storage.append_jsonl(project_id, "entities.jsonl", ent.model_dump())
            telemetry.emit(
                "entity_extracted",
                project_id=project_id,
                metadata={"type": ent.type, "confidence": ent.confidence},
            )
        telemetry.emit(
            "document_classified",
            project_id=project_id,
            metadata={"document_type": classification.document_type, "confidence": classification.confidence},
        )
        try:
            from services.intake.telemetry import emit_intake_event as emit_beta_event

            emit_beta_event(
                "evidence_mapping_confidence",
                message=classification.document_type,
                metadata={
                    "project_id": project_id,
                    "document_type": classification.document_type,
                    "confidence": classification.confidence,
                },
            )
            if classification.confidence < 0.55:
                emit_beta_event(
                    "operator_review_needed",
                    metadata={"project_id": project_id, "file": name},
                )
        except Exception:
            pass
        # Detect conflicting company names and emit telemetry
        conflicting_names = [
            c for c in profile.get("company_name_candidates") or []
            if c.get("status") == "conflicting"
        ]
        if conflicting_names:
            telemetry.emit(
                "conflicting_extraction",
                project_id=project_id,
                metadata={"field": "company_name", "count": len(conflicting_names)},
            )
            # Operator queue write — conflicting values are exactly the
            # case a human must resolve. Forensic audit (2026-06-04)
            # noted append_review_item was defined but never invoked,
            # so low-confidence and conflicting events fell on the floor.
            try:
                storage.append_review_item(project_id, {
                    "kind":       "conflicting_extraction",
                    "field":      "company_name",
                    "file":       name,
                    "artifact_id": artifact_id,
                    "count":      len(conflicting_names),
                    "candidates": [c.get("value") for c in conflicting_names][:8],
                    "created_utc": _utc_now(),
                })
            except Exception:
                pass

        result.gaps_detected = len(gaps)
        result.profile_updated = True

        for gap in gaps[:5]:
            telemetry.emit("gap_detected", project_id=project_id, metadata={"gap_id": gap.gap_id})

        confirm = needs_confirmation(profile)
        if confirm:
            telemetry.emit("customer_confirmation_needed", project_id=project_id, metadata={"count": len(confirm)})

        low = [e for e in entities if e.confidence < 0.55]
        if low:
            telemetry.emit("low_confidence_extraction", project_id=project_id, metadata={"count": len(low)})
            # Operator queue write — same reason as above; an operator
            # must decide whether to accept low-confidence extractions
            # or re-classify.
            try:
                storage.append_review_item(project_id, {
                    "kind":         "low_confidence_extraction",
                    "file":         name,
                    "artifact_id":  artifact_id,
                    "count":        len(low),
                    "samples": [
                        {"type": e.entity_type, "value": str(e.value)[:120],
                         "confidence": round(float(e.confidence), 3)}
                        for e in low[:5]
                    ],
                    "created_utc":  _utc_now(),
                })
            except Exception:
                pass

        try:
            from services.memory.organism_integration import safe_write_after_evidence_intelligence

            safe_write_after_evidence_intelligence(
                    project_id,
                    filename=name,
                    artifact_id=artifact_id,
                    sha256=actual_sha256,
                    classification=classification.model_dump(),
                entities=[e.model_dump() for e in entities],
                profile_delta=profile_to_customer_identified(profile),
                gaps=[g.gap_id for g in gaps[:10]],
                status="completed",
            )
        except Exception:
            pass

        telemetry.emit(
            "evidence_extraction_completed",
            project_id=project_id,
            metadata={"file": name, "entities": len(entities)},
        )
        telemetry.emit("profile_updated", project_id=project_id)
        result.status = "completed" if not extraction.pending_analysis else "pending_analysis"
        _record_custody_event(
            project_id,
            "evidence_intelligence_completed",
            ok=True,
            metadata={
                "file":           name,
                "artifact_id":    artifact_id,
                "sha256":         actual_sha256,
                "document_type":  classification.document_type,
                "confidence":     classification.confidence,
                "entity_count":   len(entities),
                "gap_count":      len(gaps),
            },
        )
        return result
    except Exception as e:
        result.ok = False
        result.status = "failed"
        telemetry.emit(
            "evidence_extraction_failed",
            project_id=project_id,
            success=False,
            severity="warning",
            message=str(e)[:120],
        )
        _record_custody_event(
            project_id,
            "evidence_intelligence_failed",
            ok=False,
            metadata={"file": name, "error": str(e)[:200]},
        )
        return result


def _record_custody_event(
    intake_id: str,
    phase: str,
    *,
    ok: bool = True,
    metadata: dict | None = None,
) -> None:
    """Write a custody event without ever raising into the caller.

    Doctrine: "provable chain of custody" — every event from first click
    to delivered product needs provenance. Evidence intelligence is one
    of those events; the existing transaction lifecycle ledger is the
    one true substrate, so we write straight there. In our intake-side
    pipeline `project_id == intake_id`, so the same key works for both.
    """
    try:
        from services.intake.transactions import append_transaction_event

        append_transaction_event(intake_id, phase, ok=ok, metadata=metadata or {})
    except Exception:
        return


def get_customer_evidence_profile(project_id: str) -> Dict[str, Any]:
    # See _scrub_profile_pollution / get_operator_evidence_intelligence
    # for the rationale.
    raw_profile      = storage.load_profile(project_id)
    inv_before       = len(raw_profile.get("document_inventory") or [])
    profile          = _scrub_profile_pollution(raw_profile)
    inv_after        = len(profile.get("document_inventory") or [])
    scrub_changed    = (inv_after != inv_before)
    persisted_domain = (profile.get("primary_domain") or "").strip()
    from .domains import detect_compliance_domain as _detect_domain
    if scrub_changed or not persisted_domain or persisted_domain == "general":
        _redet = _detect_domain(profile)
        if (_redet.score or 0) > 0:
            domain = _redet.domain
        elif persisted_domain and not scrub_changed:
            domain = persisted_domain
        else:
            domain = None
    else:
        _redet = None
        domain = persisted_domain
    gaps    = _enrich_gaps(detect_gaps(profile, domain=domain))
    missing = gaps[:3]
    return {
        "ok": True,
        "project_id": project_id,
        "headline": "We started organizing your paperwork",
        "identified": profile_to_customer_identified(profile),
        "needs_confirmation": needs_confirmation(profile),
        "missing_items": missing,
        "missing_items_more": len(gaps) > 3,
        "primary_domain":     domain or "general",
        "domain_confidence":  _redet.confidence if (_redet and (_redet.score or 0) > 0)
                              else (profile.get("domain_confidence") if not scrub_changed else 0.0)
                              or 0.0,
        "document_types": [
            {
                "file": row.get("file"),
                "type": row.get("document_type"),
                "confidence": row.get("confidence"),
            }
            for row in (profile.get("document_inventory") or [])[-20:]
        ],
        "confidence_summary": summarize_confidence(profile),
        "message": "We found some details in your uploads. Please confirm anything that looks right.",
    }


def confirm_entity(
    project_id: str,
    *,
    field: str,
    value: str,
    action: ConfirmAction,
) -> Dict[str, Any]:
    profile = storage.load_profile(project_id)
    bucket = field if field in profile else None
    if not bucket:
        return {"ok": False, "error": "invalid_field"}
    status_map = {"confirmed": "confirmed", "rejected": "rejected", "unsure": "unsure"}
    new_status = status_map.get(action, "unsure")
    updated = False
    for item in profile.get(bucket) or []:
        if str(item.get("value", "")).lower() == value.lower():
            item["status"] = new_status
            updated = True
    if updated:
        storage.write_profile(project_id, profile)
        evt = {
            "confirmed": "customer_confirmed_entity",
            "rejected": "customer_rejected_entity",
            "unsure": "customer_unsure_entity",
        }[new_status]
        telemetry.emit(evt, project_id=project_id, metadata={"field": field, "value": value[:80]})
        try:
            from services.memory.organism_integration import safe_write_after_evidence_confirmation

            safe_write_after_evidence_confirmation(project_id, field, value, new_status)
        except Exception:
            pass
        # Feed learning: track which field types are confirmed vs rejected
        # so operator guidance can surface "customers often confirm/reject X"
        try:
            from services.memory.central_memory import record_learning_signal

            signal_key = f"evidence_confirm:{field}:{new_status}"
            record_learning_signal(
                signal_key,
                "evidence_confirmation",
                success=(new_status == "confirmed"),
                paperwork_hint=field,
            )
        except Exception:
            pass
    return {"ok": updated, "field": field, "value": value, "status": new_status}


def reprocess_intake_evidence(
    intake_id: str,
    *,
    wipe: bool = True,
) -> Dict[str, Any]:
    """Re-run evidence intelligence for every real customer upload of an intake.

    Operator-triggered recovery / replay path. Use when:

    * An earlier deploy ran a broken EI loop and persisted polluted
      ``profile.json`` / ``classifications.jsonl`` rows that need
      rebuilding from scratch.
    * A new EI capability (OCR, domain pack, etc.) has landed and the
      operator wants to retroactively apply it to an existing intake.
    * Diagnostics: replay an intake to verify the live pipeline picks
      up the same files the customer actually uploaded.

    Behaviour:

    * ``wipe=True`` (default) calls
      :func:`services.evidence_intelligence.storage.wipe_rebuildable_artifacts`
      to delete the rebuildable EI artifacts (``profile.json``,
      ``gaps.json``, ``extractions.jsonl``, ``classifications.jsonl``,
      ``entities.jsonl``). ``review_queue.jsonl`` is intentionally
      preserved — it carries historical operator decisions that must
      survive a reprocess.
    * Lists every file under ``intakes/{intake_id}/uploads/`` and
      filters out durability sidecars (``*.durability.json``) plus the
      reserved internal filenames. Only real customer payloads are
      dispatched to :func:`process_evidence_upload`.
    * Per-file failures are caught and recorded; the loop never aborts.
    * Writes a single ``evidence_intelligence_reprocessed`` custody
      event so the chain of custody includes the reprocess action
      itself, plus a matching telemetry row.
    * Returns a structured report the operator UI / VIO can render
      without further parsing.

    Idempotent: when ``wipe=False`` and ``process_evidence_upload``
    sees a sha256 it has already completed, that file is skipped at
    the existing ``_already_processed`` gate.
    """
    iid          = (intake_id or "").strip()
    started_utc  = _utc_now()

    if not iid:
        return {
            "ok":          False,
            "intake_id":   iid,
            "error":       "intake_id_required",
            "started_utc": started_utc,
            "finished_utc": _utc_now(),
        }

    try:
        from services.intake.storage import intake_dir as _intake_dir
        uploads_dir = _intake_dir(iid) / "uploads"
    except Exception as exc:
        return {
            "ok":          False,
            "intake_id":   iid,
            "error":       f"intake_dir_failed:{type(exc).__name__}",
            "detail":      str(exc)[:200],
            "started_utc": started_utc,
            "finished_utc": _utc_now(),
        }

    if not uploads_dir.is_dir():
        return {
            "ok":          False,
            "intake_id":   iid,
            "error":       "uploads_dir_missing",
            "uploads_dir": str(uploads_dir),
            "started_utc": started_utc,
            "finished_utc": _utc_now(),
        }

    wipe_report: Dict[str, Any] = {}
    if wipe:
        try:
            wipe_report = storage.wipe_rebuildable_artifacts(iid)
        except Exception as exc:
            wipe_report = {
                "ok": False,
                "error": f"wipe_failed:{type(exc).__name__}",
                "detail": str(exc)[:200],
            }

    try:
        from services.intake.file_durability import is_upload_payload_file
        candidate_files = sorted(
            p for p in uploads_dir.iterdir()
            if p.is_file()
            and is_upload_payload_file(p.name)
            and _is_real_customer_upload(p.name)
        )
    except Exception as exc:
        return {
            "ok":          False,
            "intake_id":   iid,
            "error":       f"list_uploads_failed:{type(exc).__name__}",
            "detail":      str(exc)[:200],
            "uploads_dir": str(uploads_dir),
            "wipe":        wipe,
            "wipe_report": wipe_report,
            "started_utc": started_utc,
            "finished_utc": _utc_now(),
        }

    processed:    List[Dict[str, Any]] = []
    failed:       List[Dict[str, Any]] = []
    ocr_attempts = 0
    ocr_ok       = 0

    for f in candidate_files:
        try:
            result = process_evidence_upload(
                project_id  = iid,
                file_path   = f,
                artifact_id = f.name,
            )
            ext = result.extraction
            entry: Dict[str, Any] = {
                "file":       f.name,
                "status":     result.status,
                "entities":   result.entities_extracted,
                "gaps":       result.gaps_detected,
            }
            if ext is not None:
                entry["extraction_method"] = ext.extraction_method
                entry["text_length"]        = ext.text_length
                entry["pending_analysis"]   = bool(ext.pending_analysis)
                if ext.warnings:
                    entry["warnings"] = list(ext.warnings)[:5]
                if ext.ocr_status:
                    ocr_attempts          += 1
                    entry["ocr_status"]    = ext.ocr_status
                    entry["ocr_text_length"] = int(ext.ocr_text_length or 0)
                if ext.ocr_applied:
                    ocr_ok                += 1
                    entry["ocr_applied"]   = True
            processed.append(entry)
        except Exception as exc:
            # process_evidence_upload should never raise (it returns a
            # ProcessingResult even on failure) but defend in depth.
            failed.append({
                "file":   f.name,
                "error":  f"{type(exc).__name__}",
                "detail": str(exc)[:200],
            })

    overall_ok = (not failed)
    finished_utc = _utc_now()

    _record_custody_event(
        iid,
        "evidence_intelligence_reprocessed",
        ok=overall_ok,
        metadata={
            "wipe":          wipe,
            "wiped":         wipe_report.get("deleted") or [],
            "files_seen":    len(candidate_files),
            "files_ok":      len(processed),
            "files_failed":  len(failed),
            "ocr_attempts":  ocr_attempts,
            "ocr_succeeded": ocr_ok,
            "started_utc":   started_utc,
            "finished_utc":  finished_utc,
        },
    )

    try:
        telemetry.emit(
            "evidence_intelligence_reprocessed",
            project_id=iid,
            success=overall_ok,
            severity="info" if overall_ok else "warning",
            metadata={
                "files_seen":    len(candidate_files),
                "files_ok":      len(processed),
                "files_failed":  len(failed),
                "ocr_attempts":  ocr_attempts,
                "ocr_succeeded": ocr_ok,
            },
        )
    except Exception:
        pass

    return {
        "ok":              overall_ok,
        "intake_id":       iid,
        "wipe":            wipe,
        "wipe_report":     wipe_report,
        "uploads_dir":     str(uploads_dir),
        "files_seen":      len(candidate_files),
        "files_processed": processed,
        "files_failed":    failed,
        "ocr_attempts":    ocr_attempts,
        "ocr_succeeded":   ocr_ok,
        "started_utc":     started_utc,
        "finished_utc":    finished_utc,
    }


def get_operator_evidence_intelligence(project_id: str) -> Dict[str, Any]:
    ev_dir = DATA / "projects" / project_id / "evidence"
    intel_dir = DATA / "projects" / project_id / "evidence_intelligence"
    files = []
    if ev_dir.is_dir():
        for p in sorted(ev_dir.iterdir()):
            if p.is_file() and _is_real_customer_upload(p.name):
                files.append({"name": p.name, "size": p.stat().st_size})
    extractions_raw     = storage.load_jsonl(project_id, "extractions.jsonl", limit=200)
    classifications_raw = storage.load_jsonl(project_id, "classifications.jsonl", limit=200)
    entities_raw        = storage.load_jsonl(project_id, "entities.jsonl", limit=400)

    # Defensive filter: scrub any rows derived from internal sidecars /
    # metadata files. Earlier production runs polluted these JSONLs;
    # filtering on read means VIO and the operator dashboard show clean
    # counts without a destructive backfill.
    extractions = [
        e for e in extractions_raw
        if _is_real_customer_upload(e.get("source_file") or e.get("artifact_id") or "")
    ]
    classifications = [
        c for c in classifications_raw
        if _is_real_customer_upload(c.get("source_file") or "")
    ]
    entities = [
        e for e in entities_raw
        if _is_real_customer_upload(e.get("source_file") or "")
    ]

    raw_profile     = storage.load_profile(project_id)
    inv_before      = len(raw_profile.get("document_inventory") or [])
    profile         = _scrub_profile_pollution(raw_profile)
    inv_after       = len(profile.get("document_inventory") or [])
    scrub_changed   = (inv_after != inv_before)
    persisted_domain = (profile.get("primary_domain") or "").strip()

    # The write-time detector sees the raw extracted text and is more
    # accurate than a profile-only re-detect. We TRUST the persisted
    # domain unless either (a) the scrub removed inventory rows (meaning
    # the persisted detection may have been influenced by polluted rows
    # that are now gone), or (b) no domain was ever persisted.
    from .domains import detect_compliance_domain as _detect_domain
    if scrub_changed or not persisted_domain or persisted_domain == "general":
        _redet = _detect_domain(profile)
        if (_redet.score or 0) > 0:
            domain = _redet.domain
        elif persisted_domain and not scrub_changed:
            domain = persisted_domain
        else:
            domain = None
    else:
        _redet = None
        domain = persisted_domain
    # Always recompute gaps from the latest profile so a stale gaps.json
    # written before the domain-aware pack landed cannot mask the correct
    # rule set.
    gaps   = [g.model_dump() for g in detect_gaps(profile, domain=domain)]
    pending     = [e for e in extractions if e.get("pending_analysis")]
    failed      = [e for e in extractions if e.get("errors")]
    unsupported = [e for e in extractions if "unsupported" in str(e.get("errors", []))]

    return {
        "ok": True,
        "project_id": project_id,
        "files_uploaded": len(files),
        "files_analyzed": len(classifications),
        "pending_analysis": len(pending),
        "extraction_failures": len(failed),
        "unsupported_files": unsupported[:10],
        "document_types": classifications[-15:],
        "profile": profile_to_customer_identified(profile),
        "confidence_summary": summarize_confidence(profile),
        "missing_item_count": len(gaps),
        "gaps": gaps[:15],
        "primary_domain":     domain or "general",
        "domain_confidence":  _redet.confidence if (_redet and (_redet.score or 0) > 0)
                              else (profile.get("domain_confidence") if not scrub_changed else 0.0)
                              or 0.0,
        "domain_signals":     _redet.signals if (_redet and (_redet.score or 0) > 0)
                              else (profile.get("domain_signals") if not scrub_changed else {})
                              or {},
        "confirmation_needed": needs_confirmation(profile),
        "entity_count": len(entities),
        "artifacts_path": str(intel_dir) if intel_dir.exists() else "",
        "next_actions": _operator_next_actions(profile, gaps, pending),
    }


def _operator_next_actions(profile: Dict, gaps: List, pending: List) -> List[str]:
    actions: List[str] = []
    if pending:
        actions.append("Large or unsupported files are pending — ask customer to upload PDF/text exports if needed.")
    confirm = needs_confirmation(profile)
    if confirm:
        actions.append(f"{len(confirm)} field(s) need customer confirmation — send continuation link.")
    if gaps:
        actions.append(f"Top gap: {gaps[0].get('label') if isinstance(gaps[0], dict) else gaps[0].label} — offer example/retrieval help.")
    if not actions:
        actions.append("Review classified documents and advance scope/evidence workflow steps.")
    return actions[:5]
