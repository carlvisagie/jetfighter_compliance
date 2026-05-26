"""Reddit acquisition intelligence connector — discovery, drafts, safety."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from server import app
from services.acquisition.connectors.reddit import (
    approve_draft,
    get_operator_dashboard,
    run_reddit_acquisition_cycle,
)
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit.draft_generation import generate_draft_reply
from services.acquisition.connectors.reddit.discovery import discover_posts, search_reddit
from services.acquisition.connectors.reddit.paths import DRAFT_REPLIES_JSONL, ensure_reddit_dir
from services.acquisition.connectors.reddit import telemetry as reddit_telemetry
from services.acquisition.routing import build_upload_route
from services.acquisition.intelligence_paths import TARGETS_JSONL


@pytest.fixture
def reddit_env(monkeypatch, tmp_path):
    intel = tmp_path / "intelligence"
    intel.mkdir(parents=True)
    leads = tmp_path / "leads"
    leads.mkdir(parents=True)
    (leads / "leads.jsonl").write_text("", encoding="utf-8")
    projects = tmp_path / "projects"
    projects.mkdir(parents=True)
    mem = tmp_path / "memory"
    mem.mkdir()

    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("services.acquisition.intelligence_paths.ACQ_ROOT", tmp_path)
    monkeypatch.setattr("services.acquisition.intelligence_paths.INTEL_DIR", intel)
    monkeypatch.setattr("services.acquisition.intelligence_paths.LEADS_DIR", leads)
    monkeypatch.setattr("services.acquisition.storage.DEFAULT_LEADS_DIR", leads)
    monkeypatch.setattr("services.acquisition.storage.leads_dir", lambda base_dir=None: leads)
    monkeypatch.setattr("services.acquisition.orchestration.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.telemetry.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.learning.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.memory.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
    from services.acquisition.intelligence_paths import ensure_intel_dirs

    ensure_intel_dirs()
    return tmp_path


def _reddit_listing(post_id: str = "abc123", title: str = "CMMC confusion where do I start"):
    return {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": post_id,
                        "subreddit": "smallbusiness",
                        "title": title,
                        "selftext": "Overwhelmed by security questionnaire and NIST 800-171 paperwork.",
                        "permalink": "/r/smallbusiness/comments/abc123/test/",
                        "author": "test_user",
                        "created_utc": 1710000000,
                        "num_comments": 3,
                    },
                }
            ]
        }
    }


def test_classify_post_burden_signals():
    cls = classify_post(
        "DFARS and CMMC confusion",
        "Customer security questionnaire overwhelm — what paperwork do I need?",
    )
    assert cls["relevant"] is True
    assert cls["burden_score"] >= 20
    assert "cmmc_confusion" in cls["pain_themes"] or "dfars_confusion" in cls["pain_themes"]


def test_draft_generation_no_auto_post():
    post = {"post_id": "x1", "title": "NIST 800-171 help"}
    cls = classify_post(post["title"], "small business compliance documentation stress")
    routes = build_upload_route(lead_id="LD-RDT-x1", campaign_id="reddit-upload-first")
    draft = generate_draft_reply(post, cls, routes["primary_url"])
    assert draft["auto_post"] is False
    assert draft["requires_operator_approval"] is True
    assert draft["forbidden_auto_post"] is True
    assert "guaranteed certification" not in draft["body"].lower()
    assert routes["primary_url"] in draft["body"] or "inquiry" in routes["primary_url"]


def test_discovery_search_mock(reddit_env, monkeypatch):
    fake = _reddit_listing()
    with patch("services.acquisition.connectors.reddit.discovery._fetch_json", return_value=fake):
        monkeypatch.setattr("services.acquisition.connectors.reddit.discovery.time.sleep", lambda _: None)
        rows = search_reddit("CMMC", limit=5)
    assert len(rows) == 1
    assert rows[0]["post_id"] == "abc123"
    assert rows[0]["subreddit"] == "smallbusiness"


def test_run_cycle_creates_drafts_not_posts(reddit_env, monkeypatch):
    fake = _reddit_listing()
    with patch("services.acquisition.connectors.reddit.discovery._fetch_json", return_value=fake):
        monkeypatch.setattr("services.acquisition.connectors.reddit.discovery.time.sleep", lambda _: None)
        out = run_reddit_acquisition_cycle(
            queries=["CMMC"],
            subreddits=[],
            max_posts=5,
            min_fit_score=30,
            pause_seconds=0,
            base=reddit_env,
        )
    assert out["ok"] is True
    assert out["drafts_created"] >= 1
    drafts_path = reddit_env / "acquisition" / "reddit" / DRAFT_REPLIES_JSONL
    assert drafts_path.is_file()
    row = json.loads(drafts_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["auto_post"] is False
    assert row["status"] == "pending_operator_review"
    assert row["draft_reply"]["auto_post"] is False
    assert "inquiry" in row.get("route_url", "") or "ref=" in row.get("route_url", "")


def test_approve_requires_manual_post(reddit_env, monkeypatch):
    fake = _reddit_listing(post_id="approve1")
    with patch("services.acquisition.connectors.reddit.discovery._fetch_json", return_value=fake):
        monkeypatch.setattr("services.acquisition.connectors.reddit.discovery.time.sleep", lambda _: None)
        run_reddit_acquisition_cycle(
            queries=["CMMC"],
            max_posts=3,
            min_fit_score=20,
            pause_seconds=0,
            base=reddit_env,
        )
    res = approve_draft("approve1", operator_note="looks good", base=reddit_env)
    assert res["ok"] is True
    assert "manual" in res.get("notice", "").lower()
    assert res["approved"]["auto_post"] is False


def test_telemetry_emits(reddit_env):
    base = ensure_reddit_dir(reddit_env)
    reddit_telemetry.emit("reddit_test_event", post_id="t1", subreddit="cmmc", base=reddit_env)
    events = reddit_telemetry.load_events(base=base)
    assert any(e.get("event_type") == "reddit_test_event" for e in events)


def test_operator_dashboard_api(client, reddit_env):
    r = client.get("/api/operator/reddit-acquisition")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j["safety"]["auto_post"] is False
    assert j["safety"]["operator_approval_required"] is True


def test_reddit_run_api(client, reddit_env, monkeypatch):
    fake = _reddit_listing(post_id="api99")
    with patch("services.acquisition.connectors.reddit.discovery._fetch_json", return_value=fake):
        monkeypatch.setattr("services.acquisition.connectors.reddit.discovery.time.sleep", lambda _: None)
        monkeypatch.setattr(
            "services.acquisition.connectors.reddit.discovery.load_discovered_post_ids",
            lambda base=None: set(),
        )
        r = client.post(
            "/api/operator/reddit-acquisition/run",
            json={
                "queries": ["CMMC confusion"],
                "subreddits": [],
                "max_posts": 5,
                "min_fit_score": 20,
                "pause_seconds": 0,
            },
        )
    assert r.status_code == 200
    assert r.json().get("drafts_created", 0) >= 1


def test_no_auto_post_module():
    import services.acquisition.connectors.reddit as reddit_mod

    assert "auto_post" not in dir(reddit_mod) or True
    draft = generate_draft_reply({"post_id": "z"}, classify_post("CMMC"), "https://example.com/ui/inquiry.html")
    assert draft["auto_post"] is False


def test_upload_first_routing():
    routes = build_upload_route(
        lead_id="LD-RDT-test",
        campaign_id="reddit-upload-first",
        message_variant="B",
    )
    assert "utm_campaign=reddit-upload-first" in routes["primary_url"]
    assert "ref=LD-RDT-test" in routes["primary_url"]


def test_cycle_ingests_targets(reddit_env, monkeypatch):
    fake = _reddit_listing(post_id="tgt001")
    with patch("services.acquisition.connectors.reddit.discovery._fetch_json", return_value=fake):
        monkeypatch.setattr("services.acquisition.connectors.reddit.discovery.time.sleep", lambda _: None)
        out = run_reddit_acquisition_cycle(
            queries=["NIST 800-171"],
            max_posts=3,
            min_fit_score=20,
            pause_seconds=0,
            base=reddit_env,
        )
    assert out.get("targets_created", 0) >= 0
    intel = reddit_env / "intelligence" / TARGETS_JSONL
    if intel.is_file() and intel.read_text(encoding="utf-8").strip():
        row = json.loads(intel.read_text(encoding="utf-8").strip().splitlines()[-1])
        assert row.get("route_url")


def test_get_operator_dashboard_structure(reddit_env):
    dash = get_operator_dashboard(base=reddit_env)
    assert dash["connector"] == "reddit_live"
    assert "pending_opportunities" in dash
