import json
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from server import app
from services.security import make_founding_beta_token

@pytest.fixture
def mock_projects_dir(tmp_path):
    projects_dir = tmp_path / "data" / "projects"
    projects_dir.mkdir(parents=True)
    with patch("services.config.PROJECTS", projects_dir):
        yield projects_dir

def test_cognition_api_not_found(client, mock_projects_dir):
    project_id = "FB-123456"
    res = client.get(f"/api/operator/cognition/{project_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is False
    assert data["status"] == "not_found"
    assert data["project_id"] == project_id

def test_cognition_api_ready(client, mock_projects_dir):
    project_id = "FB-123456"
    cognition_dir = mock_projects_dir / project_id / "cognition"
    cognition_dir.mkdir(parents=True)
    
    summary = {
        "timestamp_utc": "2026-01-01T00:00:00Z",
        "state": {"knows": ["test"], "confidence_level": 0.9},
        "generated_documents": [{"doc_id": "1", "doc_type": "ssp"}]
    }
    
    (cognition_dir / "cognition_summary.json").write_text(json.dumps(summary))
    (cognition_dir / "next_actions.json").write_text(json.dumps([{"action": "do"}]))
    (cognition_dir / "cognition_events.jsonl").write_text('{"event": "start"}\n{"event": "end"}\n')
    
    res = client.get(f"/api/operator/cognition/{project_id}")
    assert res.status_code == 200
    data = res.json()
    
    assert data["ok"] is True
    assert data["status"] == "ready"
    assert data["project_id"] == project_id
    assert data["cognition_summary"] == summary
    assert len(data["next_actions"]) == 1
    assert len(data["recent_events"]) == 2
    assert len(data["generated_documents"]) == 1

def test_cognition_api_rejects_path_traversal(client, mock_projects_dir):
    project_id = "FB-123..secret"
    res = client.get(f"/api/operator/cognition/{project_id}")
    assert res.status_code == 400
    assert "project" in res.json()["detail"].lower()

def test_cognition_api_tolerates_missing_optional_files(client, mock_projects_dir):
    project_id = "FB-123456"
    cognition_dir = mock_projects_dir / project_id / "cognition"
    cognition_dir.mkdir(parents=True)
    
    summary = {
        "timestamp_utc": "2026-01-01T00:00:00Z",
        "state": {"knows": ["test"], "confidence_level": 0.9}
    }
    
    (cognition_dir / "cognition_summary.json").write_text(json.dumps(summary))
    
    res = client.get(f"/api/operator/cognition/{project_id}")
    assert res.status_code == 200
    data = res.json()
    
    assert data["ok"] is True
    assert data["status"] == "ready"
    assert data["next_actions"] == []
    assert data["recent_events"] == []
    assert data["generated_documents"] == []
