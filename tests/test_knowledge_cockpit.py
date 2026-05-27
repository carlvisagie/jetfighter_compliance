"""Knowledge Cockpit — standalone repo/runtime knowledge layer."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
SERVER = ROOT / "server.py"
SCRIPTS = ROOT / "scripts"


FORBIDDEN_RUNTIME_PATHS = [
    r"E:\\KYC\\",
    r"E:/KYC/",
    r"E:\\KYC_Library",
    r"c:\\KYC_Encyclopedia_App",
    r"C:/KYC_Encyclopedia_App",
    r"KYC_Encyclopedia_SingleFile",
]


def _runtime_sources() -> str:
    chunks = []
    for p in list(SERVICES.rglob("*.py")) + [SERVER, SCRIPTS / "import_legacy_encyclopedia.py"]:
        if not p.is_file():
            continue
        chunks.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def test_import_script_documents_legacy_only():
    text = (SCRIPTS / "import_legacy_encyclopedia.py").read_text(encoding="utf-8")
    assert "NOT called at runtime" in text or "one-time" in text.lower()


def test_no_runtime_dependency_on_legacy_encyclopedia_paths():
    scan = []
    for p in SERVICES.rglob("*.py"):
        if p.is_file():
            scan.append(p.read_text(encoding="utf-8", errors="replace"))
    if SERVER.is_file():
        scan.append(SERVER.read_text(encoding="utf-8", errors="replace"))
    blob = "\n".join(scan)
    for pat in FORBIDDEN_RUNTIME_PATHS:
        assert not re.search(pat, blob, re.I), f"Forbidden legacy path in production code: {pat}"


def test_concepts_file_in_repo():
    concepts = ROOT / "data" / "knowledge_cockpit" / "concepts.json"
    assert concepts.is_file()
    import json

    data = json.loads(concepts.read_text(encoding="utf-8"))
    assert data.get("concept_count", 0) >= 20


def test_ssp_explanation_exists():
    from services.knowledge_cockpit import explain

    out = explain(concept_id="ssp")
    assert out["ok"] is True
    assert "logbook" in (out.get("operational_meaning") or "").lower()


def test_cmmc_level_2_relationships():
    from services.knowledge_cockpit.concept_graph import related_concepts

    rel = related_concepts("cmmc-level-2")
    ids = {r.get("id") for r in rel}
    assert "nist-800-171" in ids or "cui" in ids


def test_acquisition_context_which_cmmc_level():
    from services.knowledge_cockpit.acquisition_context import build_acquisition_context

    ctx = build_acquisition_context(
        title="Which CMMC level do we need?",
        body="Small business subcontractor — customer sent a questionnaire",
        discovery_cluster="direct_cmmc",
    )
    assert ctx["ok"] is True
    assert "FCI" in ctx.get("prospect_likely_means", "") or "Level" in ctx.get("prospect_likely_means", "")
    concepts = ctx.get("related_concepts") or []
    assert any("cmmc" in (c.get("id") or "") for c in concepts)


def test_evidence_context_maps_policy():
    from services.knowledge_cockpit.evidence_context import build_evidence_context

    ctx = build_evidence_context(filename="information_security_policy.pdf", document_type="policy")
    assert ctx["primary_concept"]["id"] == "policy"


def test_telemetry_emits(client):
    from services.knowledge_cockpit.telemetry import emit_knowledge_event
    from services.memory.telemetry import load_telemetry

    emit_knowledge_event("knowledge_lookup", concept_id="ssp", query="ssp test")
    rows = load_telemetry(limit=20, subsystem="knowledge_cockpit")
    assert any(r.get("event_type") == "knowledge_lookup" for r in rows)


def test_memory_operator_learning_event():
    from services.knowledge_cockpit.memory_context import link_operator_learning
    from services.memory.central_memory import read_entity_context

    link_operator_learning("concept_explained", concept_id="mfa", metadata={"test": True})
    ctx = read_entity_context(email="operator@keepyourcontracts.internal")
    if ctx.get("known"):
        types = [t.get("event_type") for t in ctx.get("timeline") or []]
        assert "operator_learning_event" in types


def test_control_html_has_knowledge_cockpit(client):
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    assert "Knowledge Cockpit" in r.text
    assert "knowledge-cockpit-panel" in r.text
    assert "kyc-manual-knowledge" in r.text
    assert "kcExplainInput" not in r.text


def test_operator_api_protected(anon_client):
    assert anon_client.get("/api/operator/knowledge-cockpit").status_code == 403
    assert anon_client.post("/api/operator/knowledge-cockpit/explain", json={"text": "CMMC"}).status_code == 403


def test_knowledge_cockpit_api_works(client):
    r = client.get("/api/operator/knowledge-cockpit")
    assert r.status_code == 200
    assert r.json()["source"] == "repo_runtime"
    r2 = client.post("/api/operator/knowledge-cockpit/explain", json={"text": "Which CMMC level?"})
    assert r2.status_code == 200
    assert r2.json().get("ok") is True


def test_standalone_data_paths_only():
    from services.knowledge_cockpit.paths import CONCEPTS_FILE, KNOWLEDGE_DIR

    assert "knowledge_cockpit" in str(KNOWLEDGE_DIR).replace("\\", "/")
    assert CONCEPTS_FILE.is_file()


def test_contextual_overlay_reddit_five_questions():
    from services.knowledge_cockpit.contextual_overlay import build_overlay

    out = build_overlay(
        view="reddit_opportunity",
        payload={
            "title": "CMMC level 2 questionnaire help",
            "body": "Customer sent security questionnaire — overwhelmed",
            "prey_score": 72,
            "author_intent": "seeker",
            "discovery_source_cluster": "direct_cmmc",
        },
    )
    ov = out["overlay"]
    assert ov["what_am_i_looking_at"]
    assert ov["why_it_matters"]
    assert isinstance(ov["what_to_do_next"], list)


def test_migration_audit_standalone():
    from services.knowledge_cockpit.migration_audit import run_migration_audit

    report = run_migration_audit()
    assert report["standalone"] is True
    assert report["runtime_external_dependencies"] is False
    assert report["files"]["concepts"]["exists"] is True


def test_import_pipeline_requires_explicit_source():
    from services.knowledge_cockpit.import_pipeline import run_import

    out = run_import()
    assert out["ok"] is False
    assert "source_path" in out.get("error", "")


def test_overlay_api(client):
    r = client.post(
        "/api/operator/knowledge-cockpit/overlay",
        json={"view": "telemetry_signal", "payload": {"event_type": "fetch_failed", "subsystem": "reddit"}},
    )
    assert r.status_code == 200
    assert r.json()["overlay"]["what_am_i_looking_at"]


def test_control_html_has_contextual_overlay(client):
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    assert "contextual-knowledge-overlay" in r.text
    assert "contextual-knowledge-overlay.js" in r.text
    assert "ckoToggleBtn" in r.text
    assert "data-cko-panel=" in r.text
    assert "initAuto" in r.text
    assert "setPanelSnapshot" in r.text


def test_acquisition_panel_overlay():
    from services.knowledge_cockpit.contextual_overlay import build_overlay

    out = build_overlay(
        view="acquisition_panel",
        payload={
            "upload_conversion": {"rate": 0.2, "started": 5, "completed": 1},
            "hottest_targets": [{"company_name": "Acme"}],
        },
    )
    assert out["overlay"]["what_is_good_or_bad"]
    assert "real paperwork" in out["overlay"]["what_am_i_looking_at"].lower()


def test_alerts_panel_overlay():
    from services.knowledge_cockpit.contextual_overlay import build_overlay

    out = build_overlay(
        view="alerts_panel",
        payload={"config": {"telegram_configured": False, "email_enabled": False}, "unacknowledged_critical": []},
    )
    assert "Telegram" in out["overlay"]["what_am_i_looking_at"]


def test_encyclopedia_seed_in_repo():
    seed = ROOT / "data" / "knowledge_cockpit" / "encyclopedia_seed.json"
    assert seed.is_file()
