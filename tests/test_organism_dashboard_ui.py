"""UI contract tests for organism command center (control + memory)."""

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_control_html_serves_organism_command_center():
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    html = r.text
    assert "Operator cockpit" in html
    assert 'id="organism-health"' in html
    assert "Organism health" in html
    assert "organism-intel.js" in html
    assert "organism-command.css" in html
    assert 'data-org-card="memory"' in html
    assert 'data-org-feed="activity"' in html


def test_memory_html_serves_intelligence_surface():
    r = client.get("/ui/memory.html")
    assert r.status_code == 200
    html = r.text
    assert "Central organism intelligence" in html
    assert "organism-intel.js" in html
    assert 'data-org-subsystems' in html
    assert "Forensic lookup" in html
    assert 'class="codebox"' not in html or "<details" in html


def test_organism_intel_assets_served():
    for path in ("/ui/assets/js/organism-intel.js", "/ui/assets/styles/organism-command.css"):
        r = client.get(path)
        assert r.status_code == 200, path


def test_memory_apis_still_function_for_dashboard():
    endpoints = [
        "/api/memory/observability?limit=5",
        "/api/memory/learning",
        "/api/memory/self-heal",
        "/api/memory/telemetry?limit=5",
        "/api/memory/adaptive-signals?limit=5",
        "/api/memory/organism-status",
        "/api/events/recent?limit=3",
        "/health/ready",
    ]
    for path in endpoints:
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.json().get("ok") is True or "verdict" in r.json() or "checks" in r.json()


def test_observability_verdict_is_real_enum():
    r = client.get("/api/memory/observability?limit=10")
    assert r.status_code == 200
    j = r.json()
    assert j["verdict"] in (
        "organism_observable",
        "partially_observable",
        "not_observable",
    )
    assert "subsystem_health" in j
    assert isinstance(j.get("recommended_improvements"), list)


def test_self_heal_report_has_dashboard_fields():
    r = client.get("/api/memory/self-heal")
    assert r.status_code == 200
    report = r.json().get("report") or {}
    assert "entity_count" in report
    assert "orphan_projects" in report
    assert isinstance(report["orphan_projects"], list)


def test_organism_intel_js_exports_snapshot_helpers():
    r = client.get("/ui/assets/js/organism-intel.js")
    assert r.status_code == 200
    body = r.text
    assert "fetchOrganismSnapshot" in body
    assert "refreshControl" in body
    assert "/api/memory/observability" in body
    assert "recommended_improvements" in body


def test_control_html_no_debug_pre_dumps():
    r = client.get("/ui/control.html")
    assert "codebox" not in r.text
    assert '<pre id=' not in r.text
