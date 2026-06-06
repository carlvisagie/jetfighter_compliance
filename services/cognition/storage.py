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
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def run_cognition_safely(project_id: str, base_dir: Path = None) -> dict:
    if base_dir is None:
        from services.config import PROJECTS
        base_dir = PROJECTS / project_id
    
    cognition_dir = base_dir / "cognition"
    evidence_dir = base_dir / "evidence"
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
        profile = _read_json(evidence_dir / "profile.json")
        
        gaps_data = _read_json(evidence_dir / "gaps.json")
        gaps = gaps_data.get("gaps", []) if isinstance(gaps_data, dict) else (gaps_data if isinstance(gaps_data, list) else [])
        
        classifications = _read_jsonl(evidence_dir / "classifications.jsonl")
        entities = _read_jsonl(evidence_dir / "entities.jsonl")
        review_queue = _read_jsonl(evidence_dir / "review_queue.jsonl")
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
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(md_content)
                
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
        
        with open(cognition_dir / "cognition_summary.json", "w", encoding="utf-8") as f:
            f.write(summary.model_dump_json(indent=2))
            
        with open(cognition_dir / "next_actions.json", "w", encoding="utf-8") as f:
            f.write("[]")
            
        log_event("cognition_completed", {"summary_written": True})
        
        return {"status": "success", "project_id": project_id, "documents_generated": len(docs)}
        
    except Exception as e:
        logger.error("Cognition failed for project %s: %s", project_id, str(e), exc_info=True)
        log_event("cognition_failed", {"error": str(e)})
        return {"status": "error", "project_id": project_id, "error": str(e)}
