"""Continuous Compliance Intelligence Engine v1 tests."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from server import app
from services.compliance_intelligence import (
    generate_weekly_digest,
    get_operator_dashboard,
    run_compliance_cycle,
)
from services.compliance_intelligence import change_detector, classifier, fetcher, impact_mapper, sources
from services.compliance_intelligence import snapshots
from services.compliance_intelligence.schemas import ChangeRecord
from services.memory.telemetry import load_telemetry


@pytest.fixture
def ci_data(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    ci = tmp_path / "compliance_intelligence"
    ci.mkdir()

    def _mem_dir(base=None):
        return mem

    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.memory.telemetry.memory_dir", _mem_dir)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", _mem_dir)
    monkeypatch.setattr("services.memory.timeline.memory_dir", _mem_dir)
    sources.seed_sources(
        [
            {
                "source_id": "test_nist",
                "name": "Test NIST",
                "url": "https://example.com/nist",
                "authority_level": "primary",
                "topic_tags": ["nist", "800-171"],
                "polling_frequency": "daily",
                "enabled": True,
            }
        ]
    )
    return tmp_path, mem


def test_source_registry_loads(ci_data):
    loaded = sources.load_sources()
    assert len(loaded) >= 1
    assert loaded[0].source_id == "test_nist"


def test_fetcher_success(ci_data):
    html_v1 = "<html><title>NIST CMMC</title><body>SP 800-171 requirements</body></html>"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_v1
    mock_resp.headers = {}
    client = MagicMock()
    client.get.return_value = mock_resp

    src = sources.get_source("test_nist")
    result = fetcher.fetch_source(src, client=client)
    assert result.ok is True
    assert result.sha256
    assert result.snapshot_path


def test_fetcher_failure(ci_data):
    client = MagicMock()
    client.get.side_effect = httpx.TimeoutException("timeout")
    src = sources.get_source("test_nist")
    result = fetcher.fetch_source(src, client=client)
    assert result.ok is False
    assert result.error


def test_snapshot_hash_generated(ci_data):
    body = "<html><title>DFARS update</title><body>dfars 252.204</body></html>"
    result = snapshots.save_snapshot(
        "test_nist",
        body=body,
        status_code=200,
        fetched_at_utc="2026-01-01T00:00:00Z",
    )
    assert result.sha256 == snapshots.content_hash(body)


def test_change_detection_modified(ci_data):
    old = "<html><title>Old</title><body>version one</body></html>"
    new = "<html><title>New CMMC</title><body>version two cmmc update</body></html>"
    h_old = snapshots.content_hash(old)
    fetch = snapshots.save_snapshot(
        "test_nist",
        body=new,
        status_code=200,
        fetched_at_utc="2026-01-02T00:00:00Z",
    )
    change = change_detector.detect_change("test_nist", fetch, prior_hash=h_old)
    assert change is not None
    assert change.change_type in ("changed_content", "title_change", "phrase_change")


def test_classifier_tags_frameworks():
    change = ChangeRecord(
        change_id="CHG-1",
        source_id="test_nist",
        change_type="changed_content",
        diff_summary="NIST SP 800-171 and CMMC level 2 update",
    )
    clf = classifier.classify_change(change, source_tags=["nist", "cmmc"])
    assert any("CMMC" in f or "NIST" in f for f in clf.frameworks)


def test_impact_mapper_review_item(ci_data):
    change = ChangeRecord(
        change_id="CHG-2",
        source_id="test_nist",
        change_type="phrase_change",
        diff_summary="dfars clause updated",
    )
    clf = classifier.classify_change(change, source_tags=["dfars"])
    impact, review = impact_mapper.map_impact(change, clf)
    assert impact.requires_review is True
    assert impact.customer_auto_publish is False
    assert review.status == "pending"
    pending = impact_mapper.load_review_queue(status="pending")
    assert any(r.get("change_id") == "CHG-2" for r in pending)


def test_central_memory_event_written(ci_data, tmp_path):
    _tmp, mem = ci_data
    from services.compliance_intelligence import memory_bridge

    memory_bridge.write_change_detected(
        "CHG-MEM",
        "test_nist",
        {"change_type": "changed_content"},
        base=mem,
    )
    from services.memory.timeline import load_timeline
    from services.compliance_intelligence.memory_bridge import _entity_id

    eid = _entity_id(mem)
    events = [e["event_type"] for e in load_timeline(eid, base=mem)]
    assert "compliance_change_detected" in events


def test_telemetry_emitted(ci_data):
    _tmp, mem = ci_data
    from services.compliance_intelligence import telemetry

    telemetry.emit("fetch_started", metadata={"source_id": "test_nist"})
    rows = load_telemetry(subsystem="compliance_intel", base=mem)
    assert any(r["event_type"] == "fetch_started" for r in rows)


def test_operator_api_requires_auth(anon_client, ci_data):
    assert anon_client.get("/api/operator/compliance-intelligence").status_code == 403


def test_operator_api_with_auth(client, ci_data):
    r = client.get("/api/operator/compliance-intelligence")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_manual_run_protected(anon_client, client, ci_data):
    assert anon_client.post("/api/operator/compliance-intelligence/run", json={}).status_code == 403
    r = client.post("/api/operator/compliance-intelligence/run", json={"source_ids": ["test_nist"]})
    assert r.status_code == 200


def test_no_customer_auto_publication(ci_data):
    change = ChangeRecord(
        change_id="CHG-NO",
        source_id="test_nist",
        change_type="changed_content",
        diff_summary="cisa cybersecurity advisory",
    )
    clf = classifier.classify_change(change, source_tags=["cisa"])
    impact, _ = impact_mapper.map_impact(change, clf)
    assert impact.customer_auto_publish is False


def test_stale_detection(ci_data):
    sources.update_source_fields("test_nist", last_seen_utc="2020-01-01T00:00:00Z")
    stale = sources.detect_stale_sources(max_age_days=7)
    assert "test_nist" in stale


def test_digest_generation(ci_data):
    change_detector.append_change(
        ChangeRecord(
            change_id="CHG-DIG",
            source_id="test_nist",
            change_type="changed_content",
            diff_summary="test digest",
            detected_at_utc="2026-01-01T00:00:00Z",
        )
    )
    digest = generate_weekly_digest()
    assert digest.get("ok") is True
    assert digest.get("disclaimer")
    assert "not legal advice" in digest.get("disclaimer", "").lower()


def test_full_cycle_with_mock_fetch(ci_data):
    html_a = "<html><title>CMMC</title><body>alpha</body></html>"
    html_b = "<html><title>CMMC updated</title><body>pilot cmmc dfars</body></html>"

    def make_resp(text):
        r = MagicMock()
        r.status_code = 200
        r.text = text
        r.headers = {}
        return r

    client = MagicMock()
    client.get.side_effect = [make_resp(html_a), make_resp(html_b)]
    run_compliance_cycle(source_ids=["test_nist"], http_client=client)
    summary = run_compliance_cycle(source_ids=["test_nist"], http_client=client)
    assert summary.sources_checked >= 1


def test_dashboard_shape(ci_data):
    dash = get_operator_dashboard()
    assert dash.get("title")
    assert "sources" in dash
    assert dash.get("customer_auto_publish") is None  # not exposed — safety
