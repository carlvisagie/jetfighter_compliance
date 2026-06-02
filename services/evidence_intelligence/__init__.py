"""Evidence Intelligence Layer v1 — rule-based upload analysis."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from ..config import DATA
from ..public_url import get_public_base_url
from . import storage, telemetry
from .classification import classify_document
from .confidence import summarize_confidence
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
        gaps = detect_gaps(profile)
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
        return result


def get_customer_evidence_profile(project_id: str) -> Dict[str, Any]:
    profile = storage.load_profile(project_id)
    gaps = _enrich_gaps(detect_gaps(profile))
    missing = gaps[:3]
    return {
        "ok": True,
        "project_id": project_id,
        "headline": "We started organizing your paperwork",
        "identified": profile_to_customer_identified(profile),
        "needs_confirmation": needs_confirmation(profile),
        "missing_items": missing,
        "missing_items_more": len(gaps) > 3,
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


def get_operator_evidence_intelligence(project_id: str) -> Dict[str, Any]:
    ev_dir = DATA / "projects" / project_id / "evidence"
    intel_dir = DATA / "projects" / project_id / "evidence_intelligence"
    files = []
    if ev_dir.is_dir():
        for p in sorted(ev_dir.iterdir()):
            if p.is_file():
                files.append({"name": p.name, "size": p.stat().st_size})
    extractions = storage.load_jsonl(project_id, "extractions.jsonl", limit=100)
    classifications = storage.load_jsonl(project_id, "classifications.jsonl", limit=100)
    entities = storage.load_jsonl(project_id, "entities.jsonl", limit=200)
    profile = storage.load_profile(project_id)
    gaps = storage.load_gaps(project_id) or [g.model_dump() for g in detect_gaps(profile)]
    pending = [e for e in extractions if e.get("pending_analysis")]
    failed = [e for e in extractions if e.get("errors")]
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
