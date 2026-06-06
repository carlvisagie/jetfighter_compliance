import json
from pathlib import Path
from unittest.mock import patch
import pytest

from services.cognition.storage import run_cognition_safely

@pytest.fixture
def setup_project(tmp_path):
    project_id = "test_project"
    base = tmp_path / "data" / "projects" / project_id
    evidence_dir = base / "evidence"
    intel_dir = base / "evidence_intelligence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    intel_dir.mkdir(parents=True, exist_ok=True)
    
    # Mock inputs
    (intel_dir / "profile.json").write_text(json.dumps({"company_name": "Test Co", "primary_domain": "cmmc"}))
    (intel_dir / "gaps.json").write_text(json.dumps({
        "gaps": [{"gap_id": "ssp", "label": "SSP", "status": "open"}]
    }))
    (intel_dir / "entities.jsonl").write_text(json.dumps({"type": "technology", "value": "firewall", "confidence": 0.9}))
    
    return project_id, base

def test_run_cognition_safely_persists_files(setup_project):
    project_id, base = setup_project
    
    with patch("services.cognition.storage.Path") as mock_path:
        # Divert path resolutions to tmp_path
        def mock_path_factory(*args, **kwargs):
            if not args:
                return Path(*args, **kwargs)
            p = str(args[0]).replace("\\", "/")
            if p.startswith("data/projects"):
                return base.parent.parent / p
            return Path(*args, **kwargs)
        
        mock_path.side_effect = mock_path_factory
        
        # We also need to patch registry path generation
        with patch("services.cognition.storage.build_generated_document_path") as mock_build_path:
            def mock_build(proj, doc_id):
                return str(base / "evidence" / "generated_documents" / f"{doc_id}.md")
            mock_build_path.side_effect = mock_build
            
            res = run_cognition_safely(project_id, base_dir=base)
            assert res["status"] == "success"
            
            cognition_dir = base / "cognition"
            generated_dir = base / "evidence" / "generated_documents"
            
            # Cognition files exist
            assert (cognition_dir / "cognition_summary.json").exists()
            assert (cognition_dir / "next_actions.json").exists()
            assert (cognition_dir / "cognition_events.jsonl").exists()
            
            # Events logged
            events = (cognition_dir / "cognition_events.jsonl").read_text()
            assert "cognition_started" in events
            assert "awareness_synthesized" in events
            assert "gap_resolutions_created" in events
            assert "document_generation_completed" in events
            assert "document_generated" in events
            assert "cognition_completed" in events
            
            # Generated documents
            docs = list(generated_dir.glob("*.md"))
            assert len(docs) > 0
            
            content = docs[0].read_text()
            assert "DRAFT / REVIEW REQUIRED" in content
            assert "organism-generated" in content.lower()

def test_run_cognition_safely_missing_files_does_not_crash(tmp_path):
    project_id = "empty_project"
    base = tmp_path / "data" / "projects" / project_id
    
    with patch("services.cognition.storage.Path") as mock_path:
        def mock_path_factory(*args, **kwargs):
            if not args:
                return Path(*args, **kwargs)
            p = str(args[0]).replace("\\", "/")
            if p.startswith("data/projects"):
                return base.parent.parent / p
            return Path(*args, **kwargs)
        
        mock_path.side_effect = mock_path_factory
        
        # Call it with no files created in evidence_dir
        res = run_cognition_safely(project_id, base_dir=base)
        assert res["status"] == "success"
        
        cognition_dir = base / "cognition"
        assert (cognition_dir / "cognition_summary.json").exists()
        
def test_run_cognition_safely_exception_logging(tmp_path):
    project_id = "error_project"
    base = tmp_path / "data" / "projects" / project_id
    
    with patch("services.cognition.storage.Path") as mock_path:
        def mock_path_factory(*args, **kwargs):
            if not args:
                return Path(*args, **kwargs)
            p = str(args[0]).replace("\\", "/")
            if p.startswith("data/projects"):
                return base.parent.parent / p
            return Path(*args, **kwargs)
        
        mock_path.side_effect = mock_path_factory
        
        with patch("services.cognition.storage.synthesize_awareness") as mock_synth:
            mock_synth.side_effect = ValueError("Synthetic crash")
            
            res = run_cognition_safely(project_id, base_dir=base)
            assert res["status"] == "error"
            assert "Synthetic crash" in res["error"]
            
            events = (base / "cognition" / "cognition_events.jsonl").read_text()
            assert "cognition_started" in events
            assert "cognition_failed" in events
