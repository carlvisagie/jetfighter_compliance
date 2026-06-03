"""Tests for KYC Aware Organism v0 — self-awareness layer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from services.organism_state import compute_organism_state, write_organism_state_snapshot
from services.organism_state.detector import run_reconciliation_checks
from services.organism_state.health import derive_health
from services.organism_state.residue import scan_repo_for_beta_residue


# ---------- helpers ----------------------------------------------------------

def _make_intake(durable_intake_root: Path, intake_id: str, review_status: str = "pending_review", with_files: bool = True) -> Path:
    """Create a minimal valid intake record + optional upload file."""
    d = durable_intake_root / "intakes" / intake_id
    (d / "uploads").mkdir(parents=True, exist_ok=True)
    rec: Dict[str, Any] = {
        "intake_id": intake_id,
        "review_status": review_status,
        "company_name": f"Company {intake_id}",
        "submitted_utc": "2026-06-01T00:00:00Z",
        "file_count": 1 if with_files else 0,
        "uploads": [],
    }
    if with_files:
        f = d / "uploads" / "policy.pdf"
        f.write_text("dummy content", encoding="utf-8")
        rec["uploads"] = [{"filename": "policy.pdf", "size": 13}]
    (d / "intake.json").write_text(json.dumps(rec), encoding="utf-8")
    return d


# ---------- residue scanner --------------------------------------------------

def test_residue_scanner_detects_critical_package(tmp_path):
    """If services/founding_beta/__init__.py reappears, mark as CRITICAL."""
    pkg = tmp_path / "services" / "founding_beta"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("# revived shim", encoding="utf-8")
    out = scan_repo_for_beta_residue(tmp_path)
    assert out["beta_residue_detected"] is True
    assert out["critical_count"] >= 1
    assert "services/founding_beta/__init__.py" in out["critical_files"]


def test_residue_scanner_detects_imports(tmp_path):
    """Any active code importing services.founding_beta is critical residue."""
    src = tmp_path / "services" / "acquisition" / "bad.py"
    src.parent.mkdir(parents=True)
    src.write_text("from services.founding_beta.mode import is_founding_beta_mode\n", encoding="utf-8")
    out = scan_repo_for_beta_residue(tmp_path)
    assert out["beta_residue_detected"] is True
    assert any("services/acquisition/bad.py" in r for r in out["beta_imports_remaining"])
    assert out["critical_count"] >= 1


def test_residue_scanner_detects_routes(tmp_path):
    """Server routes mentioning /api/founding-beta count as critical."""
    src = tmp_path / "server.py"
    src.write_text(
        '@app.get("/api/operator/founding-beta/queue")\ndef _x(): pass\n',
        encoding="utf-8",
    )
    out = scan_repo_for_beta_residue(tmp_path)
    assert out["beta_residue_detected"] is True
    assert out["beta_routes_remaining"], "expected at least one route detected"


def test_residue_scanner_clean_repo_is_silent(tmp_path):
    """A repo with no founding_beta strings anywhere returns clean."""
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "intake.py").write_text("def ok(): return True\n", encoding="utf-8")
    out = scan_repo_for_beta_residue(tmp_path)
    assert out["beta_residue_detected"] is False
    assert out["critical_count"] == 0
    assert out["active_file_count"] == 0


def test_residue_scanner_treats_docs_as_non_critical(tmp_path):
    """Strings in docs/ or tests/ are non-runtime residue (info only)."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "history.md").write_text("# founding_beta legacy\n", encoding="utf-8")
    out = scan_repo_for_beta_residue(tmp_path)
    assert out["beta_residue_detected"] is True
    assert out["critical_count"] == 0
    assert out["docs_file_count"] >= 1


# ---------- reconciliation checks --------------------------------------------

def test_check_detects_files_hidden_from_vio():
    """If files exist but VIO shows 0 companies → RED."""
    intake = {
        "intake_count_total": 3,
        "intake_count_active": 3,
        "intake_count_archived": 0,
        "uploaded_file_count": 5,
        "queue_depth": 3,
        "queue_full_depth": 3,
        "inventory": {"intake_directories": 3, "index_tail_unique_ids": 3},
    }
    vio = {"vio_company_count": 0}
    residue = {
        "beta_residue_detected": False, "critical_count": 0,
        "active_file_count": 0, "docs_file_count": 0,
        "beta_routes_remaining": [], "beta_imports_remaining": [],
    }
    checks = run_reconciliation_checks(
        intake=intake, vio=vio,
        projects={"project_count": 0, "project_ids_sample": []},
        evidence={"evidence_artifact_count": 0},
        residue=residue,
    )
    vio_check = next(c for c in checks if c["name"] == "queue_vs_vio")
    assert vio_check["ok"] is False
    assert vio_check["severity"] == "red"


def test_check_detects_queue_mismatch():
    """If active intakes exist but queue shows 0 → RED."""
    intake = {
        "intake_count_total": 4, "intake_count_active": 4,
        "intake_count_archived": 0, "uploaded_file_count": 0,
        "queue_depth": 0, "queue_full_depth": 0,
        "inventory": {"intake_directories": 4, "index_tail_unique_ids": 4},
    }
    checks = run_reconciliation_checks(
        intake=intake,
        vio={"vio_company_count": 0},
        projects={"project_count": 0, "project_ids_sample": []},
        evidence={"evidence_artifact_count": 0},
        residue={
            "beta_residue_detected": False, "critical_count": 0,
            "active_file_count": 0, "docs_file_count": 0,
            "beta_routes_remaining": [], "beta_imports_remaining": [],
        },
    )
    q = next(c for c in checks if c["name"] == "intake_index_vs_queue")
    assert q["ok"] is False
    assert q["severity"] == "red"


def test_check_detects_evidence_vs_files_mismatch():
    """If files uploaded but no evidence extracted → RED."""
    intake = {
        "intake_count_total": 1, "intake_count_active": 1,
        "intake_count_archived": 0, "uploaded_file_count": 5,
        "queue_depth": 1, "queue_full_depth": 1,
        "inventory": {"intake_directories": 1, "index_tail_unique_ids": 1},
    }
    checks = run_reconciliation_checks(
        intake=intake, vio={"vio_company_count": 1},
        projects={"project_count": 0, "project_ids_sample": []},
        evidence={"evidence_artifact_count": 0},
        residue={
            "beta_residue_detected": False, "critical_count": 0,
            "active_file_count": 0, "docs_file_count": 0,
            "beta_routes_remaining": [], "beta_imports_remaining": [],
        },
    )
    e = next(c for c in checks if c["name"] == "evidence_vs_files")
    assert e["ok"] is False
    assert e["severity"] == "red"


def test_check_detects_healthy_empty_state():
    """A pristine empty platform should report GREEN across the board."""
    intake = {
        "intake_count_total": 0, "intake_count_active": 0,
        "intake_count_archived": 0, "uploaded_file_count": 0,
        "queue_depth": 0, "queue_full_depth": 0,
        "inventory": {
            "intake_directories": 0, "index_tail_unique_ids": 0,
            "only_on_disk_not_in_index": [], "only_in_index_not_on_disk": [],
        },
    }
    residue = {
        "beta_residue_detected": False, "critical_count": 0,
        "active_file_count": 0, "docs_file_count": 0,
        "beta_routes_remaining": [], "beta_imports_remaining": [],
    }
    checks = run_reconciliation_checks(
        intake=intake, vio={"vio_company_count": 0},
        projects={"project_count": 0, "project_ids_sample": []},
        evidence={"evidence_artifact_count": 0},
        residue=residue,
    )
    health, bottleneck, _, mismatches = derive_health(
        checks,
        intake=intake,
        storage={"durable_storage_configured": True, "environment": "test"},
    )
    assert health == "GREEN"
    assert mismatches == []
    assert bottleneck == "none"


def test_check_detects_healthy_active_state():
    """Files + matching queue + matching VIO + evidence → GREEN."""
    intake = {
        "intake_count_total": 2, "intake_count_active": 2,
        "intake_count_archived": 0, "uploaded_file_count": 4,
        "queue_depth": 2, "queue_full_depth": 2,
        "inventory": {
            "intake_directories": 2, "index_tail_unique_ids": 2,
            "only_on_disk_not_in_index": [], "only_in_index_not_on_disk": [],
        },
    }
    residue = {
        "beta_residue_detected": False, "critical_count": 0,
        "active_file_count": 0, "docs_file_count": 0,
        "beta_routes_remaining": [], "beta_imports_remaining": [],
    }
    checks = run_reconciliation_checks(
        intake=intake, vio={"vio_company_count": 2},
        projects={"project_count": 1, "project_ids_sample": ["P-1"]},
        evidence={"evidence_artifact_count": 7},
        residue=residue,
    )
    health, _, action, _ = derive_health(
        checks,
        intake=intake,
        storage={"durable_storage_configured": True, "environment": "test"},
    )
    assert health == "GREEN"
    assert "queue" in action.lower() or "review" in action.lower()


def test_check_detects_beta_residue():
    """Critical beta residue forces RED health."""
    intake = {
        "intake_count_total": 0, "intake_count_active": 0,
        "intake_count_archived": 0, "uploaded_file_count": 0,
        "queue_depth": 0, "queue_full_depth": 0,
        "inventory": {
            "intake_directories": 0, "index_tail_unique_ids": 0,
            "only_on_disk_not_in_index": [], "only_in_index_not_on_disk": [],
        },
    }
    residue = {
        "beta_residue_detected": True, "critical_count": 3,
        "active_file_count": 2, "docs_file_count": 0,
        "beta_routes_remaining": ["server.py:/api/operator/founding-beta/queue"],
        "beta_imports_remaining": ["services/acquisition/x.py"],
    }
    checks = run_reconciliation_checks(
        intake=intake, vio={"vio_company_count": 0},
        projects={"project_count": 0, "project_ids_sample": []},
        evidence={"evidence_artifact_count": 0},
        residue=residue,
    )
    health, bottleneck, _, _ = derive_health(
        checks,
        intake=intake,
        storage={"durable_storage_configured": True, "environment": "test"},
    )
    assert health == "RED"
    assert bottleneck == "beta_residue_scan"


# ---------- end-to-end -------------------------------------------------------

def test_compute_organism_state_returns_required_fields(durable_intake_root):
    """The full snapshot must include every field the spec requires."""
    _make_intake(durable_intake_root, "FB-aware-001", review_status="pending_review", with_files=True)
    state = compute_organism_state()
    required = {
        "timestamp_utc", "git_commit", "deploy_commit", "environment",
        "data_root", "durable_storage_configured", "intake_count_total",
        "intake_count_active", "intake_count_archived", "uploaded_file_count",
        "evidence_artifact_count", "project_count", "queue_depth",
        "vio_company_count", "control_queue_count", "beta_residue_detected",
        "beta_routes_remaining", "beta_files_remaining", "visibility_mismatches",
        "health_state", "current_bottleneck", "next_recommended_action",
    }
    missing = required - set(state.keys())
    assert not missing, f"missing required fields: {missing}"
    assert state["health_state"] in ("GREEN", "AMBER", "RED")
    assert state["intake_count_total"] >= 1


def test_endpoint_requires_ops_auth(anon_client):
    """The endpoint must be 403 for anonymous callers."""
    r = anon_client.get("/api/operator/organism/state")
    assert r.status_code == 403


def test_endpoint_returns_state_for_operator(client, durable_intake_root):
    """An authenticated operator receives a valid snapshot."""
    _make_intake(durable_intake_root, "FB-aware-002", review_status="pending_review", with_files=True)
    r = client.get("/api/operator/organism/state")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "health_state" in body
    assert body["health_state"] in ("GREEN", "AMBER", "RED")


def test_snapshot_persisted_to_disk(durable_intake_root, tmp_path):
    """write_organism_state_snapshot must produce a readable JSON file."""
    state = compute_organism_state()
    target = tmp_path / "organism_state.json"
    write_organism_state_snapshot(state, path=target)
    assert target.is_file()
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert on_disk["health_state"] == state["health_state"]
