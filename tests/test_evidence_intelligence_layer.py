"""Evidence Intelligence Layer v1 tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app
from services.customer_friction import issue_continuation
from services.evidence_intelligence import (
    confirm_entity,
    get_customer_evidence_profile,
    get_operator_evidence_intelligence,
    process_evidence_upload,
)
from services.evidence_intelligence.classification import classify_document
from services.evidence_intelligence.entities import extract_entities
from services.evidence_intelligence.extraction import extract_from_file, redact_secrets
from services.evidence_intelligence import storage
from services.evidence_intelligence.profile import update_profile
from services.evidence_intelligence.classification import ClassificationResult
from services.memory.telemetry import load_telemetry


@pytest.fixture
def ei_client(client):
    return client


@pytest.fixture
def ei_project(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()

    def _mem_dir(base=None):
        return mem

    monkeypatch.setattr("services.memory.telemetry.memory_dir", _mem_dir)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", _mem_dir)
    monkeypatch.setattr("services.memory.timeline.memory_dir", _mem_dir)
    projects = tmp_path / "projects"
    pid = "P-EI-TEST"
    pdir = projects / pid
    (pdir / "evidence").mkdir(parents=True)
    (pdir / "meta.json").write_text(
        json.dumps({"project_id": pid, "customer": {"email": "ei@test.com", "name": "EI Co"}})
    )
    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("services.production.PROJECTS", projects)
    cont = issue_continuation(pid, "ei@test.com")
    return pid, cont["continuation_token"], tmp_path, mem


def test_extracts_email_domain_from_text(tmp_path):
    f = tmp_path / "contacts.txt"
    f.write_text("Contact ops@acme-defense.com and visit https://www.acme-defense.com", encoding="utf-8")
    ext = extract_from_file(f)
    ents = extract_entities(ext.text_preview, f.name)
    types = {e.type for e in ents}
    assert "email" in types
    assert "domain" in types


def test_classifies_mfa_evidence():
    clf = classify_document("Multi-factor authentication is enabled for all users", "mfa_settings.png")
    assert clf.document_type in ("mfa_evidence", "screenshot")


def test_classifies_training_record():
    clf = classify_document("Security awareness training completed for all staff", "training_report.pdf")
    assert clf.document_type == "training_record"


def test_detects_compliance_references():
    ents = extract_entities("We align with CMMC Level 2 and NIST SP 800-171", "scope.txt")
    vals = [e.value for e in ents]
    assert any("CMMC" in v or "NIST" in v for v in vals)


def test_builds_profile_with_confidence(ei_project):
    pid, _, _, _mem = ei_project
    profile = storage.load_profile(pid)
    from services.evidence_intelligence.entities import _item

    ents = extract_entities("ops@acme.com", "note.txt")
    clf = ClassificationResult(document_type="policy", confidence=0.7, source_file="note.txt")
    update_profile(profile, ents, clf)
    storage.write_profile(pid, profile)
    loaded = storage.load_profile(pid)
    assert loaded.get("emails") or loaded.get("document_inventory")


def test_emits_telemetry(ei_project):
    pid, _, tmp, mem = ei_project
    f = tmp / "projects" / pid / "evidence" / "mfa.txt"
    f.write_text("MFA and 2FA required for all accounts", encoding="utf-8")
    process_evidence_upload(pid, f)
    rows = load_telemetry(subsystem="evidence_intelligence", base=mem)
    assert any(r["event_type"] == "evidence_extraction_completed" for r in rows)


def test_writes_project_artifacts(ei_project):
    pid, _, tmp, _mem = ei_project
    f = tmp / "projects" / pid / "evidence" / "policy.txt"
    f.write_text("Information security policy v1", encoding="utf-8")
    process_evidence_upload(pid, f)
    intel = tmp / "projects" / pid / "evidence_intelligence"
    assert (intel / "profile.json").is_file()
    assert (intel / "extractions.jsonl").is_file()


def test_links_central_memory_timeline(ei_project):
    pid, _, tmp, base = ei_project
    from services.memory.central_memory import link_project, find_entity_id, resolve_or_create_entity
    eid = resolve_or_create_entity(email="ei@test.com", company="EI Co", base=base)
    link_project(pid, eid, base=base)
    f = tmp / "projects" / pid / "evidence" / "doc.txt"
    f.write_text("vendor management policy", encoding="utf-8")
    process_evidence_upload(pid, f, sha256="a" * 64)
    eid2 = find_entity_id(project_id=pid, base=base)
    assert eid2
    from services.memory.timeline import load_timeline

    events = [e["event_type"] for e in load_timeline(eid2, base=base)]
    assert "evidence_analyzed" in events


def test_customer_profile_with_token(ei_client, ei_project):
    pid, tok, tmp, _mem = ei_project
    f = tmp / "projects" / pid / "evidence" / "info.txt"
    f.write_text("Contact hello@example.org", encoding="utf-8")
    process_evidence_upload(pid, f)
    r = ei_client.get(f"/api/customer/evidence/profile?project_id={pid}&token={tok}")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert "identified" in j


def test_blocks_invalid_token(ei_client, ei_project):
    pid, _, _, _mem = ei_project
    r = ei_client.get(f"/api/customer/evidence/profile?project_id={pid}&token=bad")
    assert r.status_code == 403


def test_operator_requires_auth(ei_client, ei_project):
    pid, _, _, _mem = ei_project
    anon = TestClient(app)
    assert anon.get(f"/api/operator/evidence-intelligence?project_id={pid}").status_code == 403
    assert ei_client.get(f"/api/operator/evidence-intelligence?project_id={pid}").status_code == 200


def test_missing_items_have_example_urls(ei_project):
    pid, _, _, _mem = ei_project
    prof = get_customer_evidence_profile(pid)
    missing = prof.get("missing_items") or []
    assert len(missing) <= 3
    if missing:
        assert missing[0].get("example_url")


def test_redacts_secrets():
    raw = "api_key=sk-live-abcdefghijklmnop and password=SuperSecret123!"
    out = redact_secrets(raw)
    assert "SuperSecret123" not in out
    assert "[REDACTED]" in out


def test_unsupported_file_no_crash(ei_project):
    pid, _, tmp, _mem = ei_project
    f = tmp / "projects" / pid / "evidence" / "malware.exe"
    f.write_bytes(b"MZ")
    proc = process_evidence_upload(pid, f)
    assert proc.ok is True or proc.status in ("pending_analysis", "failed", "completed")


def test_no_hallucinated_company_name():
    ents = extract_entities("This document has no organization name at all.", "plain.txt")
    companies = [e for e in ents if e.type == "company_name"]
    assert len(companies) == 0


def test_duplicate_upload_safe(ei_project):
    pid, _, tmp, _mem = ei_project
    f = tmp / "projects" / pid / "evidence" / "dup.txt"
    f.write_text("ops@dup.com", encoding="utf-8")
    process_evidence_upload(pid, f)
    process_evidence_upload(pid, f)
    ents = storage.load_jsonl(pid, "entities.jsonl")
    emails = [r for r in ents if r.get("type") == "email"]
    assert len(emails) >= 1


def test_upload_pipeline_still_works(ei_client, ei_project):
    pid, tok, tmp, _mem = ei_project
    f = tmp / "sample.txt"
    f.write_text("policy document", encoding="utf-8")
    with f.open("rb") as fh:
        r = ei_client.post(
            f"/api/evidence/register?project_id={pid}&media_type=document&owner=ei@test.com&token={tok}",
            files={"file": ("sample.txt", fh, "text/plain")},
        )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_no_public_ops_leakage(anon_client):
    r = anon_client.get("/api/operator/evidence-intelligence?project_id=P-X")
    assert r.status_code in (401, 403)


# ── Refinement tests added for bulletproof spec coverage ─────────────────────


def test_cross_file_profile_building(ei_project):
    """Company name from file A and email from file B must both appear in profile."""
    pid, _, tmp, _mem = ei_project

    f_a = tmp / "projects" / pid / "evidence" / "contract.txt"
    f_a.write_text("Acme Defense LLC signed this agreement on 2024-01-15.", encoding="utf-8")

    f_b = tmp / "projects" / pid / "evidence" / "contacts.txt"
    f_b.write_text("Primary contact: jane@acme-defense.com for all inquiries.", encoding="utf-8")

    process_evidence_upload(pid, f_a)
    process_evidence_upload(pid, f_b)

    prof = get_customer_evidence_profile(pid)
    identified = prof.get("identified") or {}
    assert any("Acme" in n for n in identified.get("company_names", [])), (
        "company name from file A must be in profile"
    )
    assert any("jane@acme-defense.com" in e for e in identified.get("emails", [])), (
        "email from file B must be in profile"
    )


def test_confirmation_status_persists(ei_project):
    """After customer confirms an entity its status must be 'confirmed' on next profile load."""
    pid, _, tmp, _mem = ei_project

    f = tmp / "projects" / pid / "evidence" / "domain.txt"
    f.write_text("Visit us at https://www.acme-ops.com for more info.", encoding="utf-8")
    process_evidence_upload(pid, f)

    # Retrieve first, find the domain to confirm
    prof = get_customer_evidence_profile(pid)
    domains = prof.get("identified", {}).get("domains", [])
    assert domains, "at least one domain should be extracted"

    target = domains[0]
    confirm_entity(pid, field="domains", value=target, action="confirmed")

    # Reload profile — status must be confirmed now
    profile = storage.load_profile(pid)
    confirmed = [
        d for d in (profile.get("domains") or [])
        if d.get("value", "").lower() == target.lower() and d.get("status") == "confirmed"
    ]
    assert confirmed, f"domain '{target}' should be confirmed in profile, got: {profile.get('domains')}"


def test_conflicting_company_names_detected(ei_project):
    """Two uploads with different company legal names must trigger conflicting status."""
    pid, _, tmp, _mem = ei_project

    f_a = tmp / "projects" / pid / "evidence" / "doc_a.txt"
    f_a.write_text("This policy is issued by Acme Defense LLC.", encoding="utf-8")

    f_b = tmp / "projects" / pid / "evidence" / "doc_b.txt"
    f_b.write_text("Agreement between Pilot Industries Inc and client.", encoding="utf-8")

    process_evidence_upload(pid, f_a)
    process_evidence_upload(pid, f_b)

    profile = storage.load_profile(pid)
    candidates = profile.get("company_name_candidates") or []
    conflicting = [c for c in candidates if c.get("status") == "conflicting"]

    # At least one should be conflicting since two distinct company names were found
    assert conflicting, (
        f"Expected conflicting company names, got statuses: "
        f"{[c.get('status') for c in candidates]}"
    )
    # And needs_confirmation must surface them with status='conflicting'
    from services.evidence_intelligence.profile import needs_confirmation
    confirm_items = needs_confirmation(profile)
    conflict_items = [i for i in confirm_items if i.get("status") == "conflicting"]
    assert conflict_items, "conflicting company names must appear in needs_confirmation list"


def test_review_queue_persists_conflicting_extractions(ei_project):
    """REGRESSION GUARD — EI must write conflicting extractions to the
    operator review queue, not just emit telemetry.

    Forensic audit (2026-06-04) flagged that `append_review_item`
    existed but was never invoked, so low-confidence and conflicting
    events were fire-and-forget telemetry. This guard pins the wiring.
    """
    pid, _, tmp, _mem = ei_project

    f_a = tmp / "projects" / pid / "evidence" / "conflict_a.txt"
    f_a.write_text("This policy is issued by Acme Defense LLC.",
                   encoding="utf-8")
    f_b = tmp / "projects" / pid / "evidence" / "conflict_b.txt"
    f_b.write_text("Agreement between Pilot Industries Inc and client.",
                   encoding="utf-8")

    process_evidence_upload(pid, f_a)
    process_evidence_upload(pid, f_b)

    queue = storage.load_review_queue(pid)
    kinds = {item.get("kind") for item in queue}
    assert "conflicting_extraction" in kinds, (
        "conflicting company-name detection must enqueue a review item; "
        "got kinds=%r" % (kinds,)
    )


def test_review_queue_operator_endpoint_reads_by_intake_id(
    ei_client, ei_project
):
    """REGRESSION GUARD — operator endpoint must accept intake_id
    (the current pipeline key) in addition to legacy project_id."""
    pid, _, _tmp, _mem = ei_project
    storage.append_review_item(pid, {
        "kind": "low_confidence_extraction",
        "file": "smoke.pdf",
        "count": 3,
        "created_utc": "2026-06-04T00:00:00Z",
    })

    r = ei_client.get(
        "/api/operator/evidence-intelligence/review-queue",
        params={"intake_id": pid},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("count") >= 1
    assert any(
        i.get("kind") == "low_confidence_extraction"
        for i in body.get("items") or []
    )
