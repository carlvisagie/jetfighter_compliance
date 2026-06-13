import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from services.cognition.synthesis import synthesize_awareness
from services.cognition.reasoning import evaluate_all_gaps
from services.cognition.document_generation.engine import generate_documents_for_resolutions
from services.cognition.schemas import CognitionSummary, MemoryReasoning
from services.cognition.metrics import compute_metrics
from services.cognition.validation import build_validation_report
from services.cognition.scorecard import calculate_scorecard, evaluate_launch_gate
from services.cognition.document_generation.registry import (
    build_generated_document_path, 
    generated_document_to_markdown, 
    build_document_registry_event
)

logger = logging.getLogger(__name__)

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _read_json(path: str | Path) -> Any:
    path = Path(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _read_jsonl(path: str | Path) -> list:
    path = Path(path)
    res = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        res.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return res

def _append_jsonl(path: str | Path, record: dict):
    """Append to JSONL with defensive error telemetry."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        # CRITICAL: File write failed (disk full, permissions, I/O error)
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                "cognition",
                "jsonl_write_failed",
                severity="critical",
                metadata={
                    "path": str(path),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception:
            pass
        raise

def get_cognition_state(project_id: str) -> dict:
    from services.durable_storage import active_data_root
    base_dir = active_data_root() / "projects" / project_id
    cognition_dir = base_dir / "cognition"
    evidence_dir = base_dir / "evidence"
    
    summary_path = cognition_dir / "cognition_summary.json"
    next_actions_path = cognition_dir / "next_actions.json"
    events_path = cognition_dir / "cognition_events.jsonl"
    metrics_path = cognition_dir / "metrics.json"
    validation_path = cognition_dir / "validation_report.json"
    score_path = cognition_dir / "organism_score.json"
    gate_path = cognition_dir / "launch_gate.json"
    
    if not summary_path.exists():
        return {
            "ok": False,
            "status": "not_found",
            "project_id": project_id,
            "message": "Cognition has not run for this project."
        }
        
    summary = _read_json(summary_path)
    next_actions = _read_json(next_actions_path) if next_actions_path.exists() else []
    events = _read_jsonl(events_path) if events_path.exists() else []
    metrics = _read_json(metrics_path) if metrics_path.exists() else {}
    validation_report = _read_json(validation_path) if validation_path.exists() else {}
    organism_score = _read_json(score_path) if score_path.exists() else {}
    launch_gate = _read_json(gate_path) if gate_path.exists() else {}
    
    # get generated documents metadata
    generated_docs = []
    if "generated_documents" in summary:
        generated_docs = summary["generated_documents"]
    elif summary_path.exists():
        generated_docs = []
        
    recent_events = events[-10:] if events else []
    
    return {
        "ok": True,
        "status": "ready",
        "project_id": project_id,
        "cognition_summary": summary,
        "next_actions": next_actions,
        "generated_documents": generated_docs,
        "recent_events": recent_events,
        "metrics": metrics,
        "validation_report": validation_report,
        "organism_score": organism_score,
        "launch_gate": launch_gate
    }

def run_cognition_safely(project_id: str, base_dir: Path = None) -> dict:
    if base_dir is None:
        from services.durable_storage import active_data_root
        base_dir = active_data_root() / "projects" / project_id
    
    cognition_dir = base_dir / "cognition"
    evidence_dir = base_dir / "evidence"
    intel_dir = base_dir / "evidence_intelligence"
    generated_dir = evidence_dir / "generated_documents"
    events_file = cognition_dir / "cognition_events.jsonl"
    
    cognition_dir.mkdir(parents=True, exist_ok=True)
    generated_dir.mkdir(parents=True, exist_ok=True)
    
    def log_event(event_type: str, details: dict = None):
        evt = {
            "event_id": f"cog_{uuid.uuid4().hex[:8]}",
            "timestamp_utc": _utc_now(),
            "event_type": event_type,
            "project_id": project_id
        }
        if details:
            evt.update(details)
        try:
            _append_jsonl(events_file, evt)
        except Exception as e:
            logger.warning("Failed to log cognition event: %s", e)

    log_event("cognition_started")
    
    try:
        # 1. Load inputs
        profile = _read_json(intel_dir / "profile.json")
        
        gaps_data = _read_json(intel_dir / "gaps.json")
        gaps = gaps_data.get("gaps", []) if isinstance(gaps_data, dict) else (gaps_data if isinstance(gaps_data, list) else [])
        
        classifications = _read_jsonl(intel_dir / "classifications.jsonl")
        entities = _read_jsonl(intel_dir / "entities.jsonl")
        review_queue = _read_jsonl(intel_dir / "review_queue.jsonl")
        timelines = _read_jsonl(evidence_dir / "timelines.jsonl")
        
        # 2. Synthesis
        state = synthesize_awareness(
            profile=profile,
            classifications=classifications,
            entities=entities,
            gaps=gaps,
            review_queue=review_queue,
            timeline=timelines
        )
        log_event("awareness_synthesized", {"confidence_level": state.confidence_level})
        
        # 3. Reasoning
        resolutions = evaluate_all_gaps(gaps, state)
        print(f"GAPS: {gaps}, RESOLUTIONS: {len(resolutions)}")
        log_event("gap_resolutions_created", {"resolution_count": len(resolutions)})
        
        # 4. Document Generation
        docs = generate_documents_for_resolutions(resolutions, state)
        print(f"DOCS GENERATED: {len(docs)}")
        log_event("document_generation_completed", {"document_count": len(docs)})
        
        # 5. Persist Output
        for doc in docs:
            md_content = generated_document_to_markdown(doc)
            # Requirements: "Must be marked as organism-generated."
            # Our registry template already adds "DRAFT / REVIEW REQUIRED" and provenance, 
            # let's explicitly make sure it has organism-generated note.
            if "organism-generated" not in md_content.lower():
                md_content += "\n\n---\n*This document is organism-generated.*"
                
            doc_path = build_generated_document_path(project_id, doc.doc_id)
            Path(doc_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Write document with defensive framework
            safe_write_text(
                Path(doc_path),
                md_content,
                component="cognition",
                context=f"project {project_id} document {doc.doc_id}",
                severity="critical"
            )
                
            registry_evt = build_document_registry_event(doc, project_id)
            log_event("document_persisted", registry_evt)
        
        summary = CognitionSummary(
            timestamp_utc=_utc_now(),
            state=state,
            memory=MemoryReasoning(trajectory="steady", changed_since_last_run=[]),
            gap_resolutions=resolutions,
            generated_documents=docs,
            next_actions=[],
            drafts=[]
        )
        
        # Write all cognition output files with defensive error handling
        # Write all cognition output files with defensive framework
        safe_write_text(
            cognition_dir / "cognition_summary.json",
            summary.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} summary",
            severity="critical"
        )
        
        safe_write_text(
            cognition_dir / "next_actions.json",
            "[]",
            component="cognition",
            context=f"project {project_id} next_actions",
            severity="critical"
        )
            
        # 6. Write generation_explanation.json
        explanations = []
        for res in resolutions:
            explanations.append({
                "Gap": res.gap_id,
                "Resolution": res.strategy.value.upper(),
                "Confidence": res.confidence,
                "Evidence Used": res.evidence_used,
                "Unresolved": res.missing_fields,
                "Reason": res.reason_unresolved,
                "Purpose": "The organism must be able to explain every document it generates and every question it asks. No black-box behavior."
            })
            
        # Write explanation with defensive framework  
        safe_write_json(
            cognition_dir / "generation_explanation.json",
            explanations,
            component="cognition",
            context=f"project {project_id} generation_explanation",
            severity="warning"
        )
            
        # Write metrics with defensive framework
        metrics = compute_metrics(state, resolutions)
        safe_write_text(
            cognition_dir / "metrics.json",
            metrics.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} metrics",
            severity="warning"
        )
            
        # 8. Write validation_report.json
        # PATCH 13A-4F: Emit validation_started
        try:
            from services.intake.telemetry import emit_lifecycle_event
            emit_lifecycle_event(
                "validation_started",
                message=f"Starting validation for {project_id}",
                metadata={"project_id": project_id},
            )
        except Exception:
            pass
        
        # Write validation report with defensive framework
        validation = build_validation_report(project_id, state, resolutions, docs)
        safe_write_text(
            cognition_dir / "validation_report.json",
            validation.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} validation_report",
            severity="critical"
        )
        
        # PATCH 13A-4F: Emit validation_completed
        try:
            emit_lifecycle_event(
                "validation_completed",
                message=f"Validation completed for {project_id}",
                metadata={
                    "project_id": project_id,
                    "human_review_items": len(validation.human_review_items),
                    "safety_warnings": len(validation.safety_warnings),
                },
            )
        except Exception:
            pass
            
        # Write organism_score and launch_gate with defensive framework
        scorecard = calculate_scorecard(state, metrics, validation)
        safe_write_text(
            cognition_dir / "organism_score.json",
            scorecard.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} organism_score",
            severity="critical"
        )
        
        gate = evaluate_launch_gate(scorecard, metrics, validation)
        safe_write_text(
            cognition_dir / "launch_gate.json",
            gate.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} launch_gate",
            severity="critical"
        )
            
        log_event("cognition_completed", {"summary_written": True})
        
        return {"status": "success", "project_id": project_id, "documents_generated": len(docs)}
        
    except Exception as e:
        logger.error("Cognition failed for project %s: %s", project_id, str(e), exc_info=True)
        log_event("cognition_failed", {"error": str(e)})
        return {"status": "error", "project_id": project_id, "error": str(e)}
