"""Regression: /api/operator/evidence-intelligence accepts FB-* intake IDs.

THE INCIDENT (2026-06-05)
   While verifying the autonomous EI reprocess on production, the
   operator EI snapshot endpoint returned:

     GET /api/operator/evidence-intelligence?project_id=FB-1dfab13c120b
     → 400 {"detail": "Invalid project_id"}

   The endpoint was wired through `validate_project_id` which rejects
   anything that doesn't start with `P-`. But the founding-beta
   pipeline keys its EI artifacts on `FB-*` intake IDs — and that's
   the only pipeline currently in production. Operators had no path
   to view EI for any FB intake.

THE FIX
   The endpoint now accepts BOTH `intake_id` (the new param) and
   `project_id` (legacy). The validator is local: allow `P-*` OR
   `FB-*`, reject `/`, `\\`, and `..`. The full project-existence
   check the legacy validator imposed isn't needed here — the EI
   loader handles missing artifacts gracefully and returns an empty
   snapshot.

This guard pins:
   · `?project_id=FB-*` returns 200, not 400 (the regression bug)
   · `?intake_id=FB-*` works (the new, correct parameter name)
   · `?project_id=P-*` still works (legacy compatibility)
   · Junk IDs and path-traversal attempts are still rejected
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


OPS_KEY = "prod-test-key"


@pytest.fixture
def authed_client(monkeypatch):
    """Test client with the ops-auth gate satisfied."""
    monkeypatch.setenv("OPS_API_KEY", OPS_KEY)
    from server import app
    return TestClient(app)


def _get(c, path):
    return c.get(path, headers={"X-Ops-Key": OPS_KEY})


def test_endpoint_accepts_fb_intake_via_project_id_param(authed_client):
    """The exact request that broke on production (?project_id=FB-…)
    must now succeed. Returns the structured EI snapshot (possibly
    empty if no artifacts) — NOT 400."""
    r = _get(authed_client, "/api/operator/evidence-intelligence?project_id=FB-test12345678")
    assert r.status_code == 200, (
        f"endpoint must accept FB-* via project_id (legacy param). "
        f"Got {r.status_code}: {r.text[:300]}"
    )


def test_endpoint_accepts_fb_intake_via_intake_id_param(authed_client):
    """The new, correctly-named parameter must also work."""
    r = _get(authed_client, "/api/operator/evidence-intelligence?intake_id=FB-test12345678")
    assert r.status_code == 200, (
        f"endpoint must accept FB-* via intake_id. "
        f"Got {r.status_code}: {r.text[:300]}"
    )


def test_endpoint_accepts_legacy_project_ids(authed_client):
    """Backward compat: P-* IDs must still work."""
    r = _get(authed_client, "/api/operator/evidence-intelligence?project_id=P-legacytest")
    assert r.status_code == 200, (
        f"endpoint must remain compatible with P-* IDs. "
        f"Got {r.status_code}: {r.text[:300]}"
    )


def test_endpoint_rejects_missing_id(authed_client):
    r = _get(authed_client, "/api/operator/evidence-intelligence")
    body = r.json()
    assert body.get("ok") is False
    assert "required" in (body.get("error") or "").lower()


def test_endpoint_rejects_bad_prefix(authed_client):
    r = _get(authed_client, "/api/operator/evidence-intelligence?intake_id=XYZ-abc")
    body = r.json()
    assert body.get("ok") is False
    assert "P-" in (body.get("error") or "") or "FB-" in (body.get("error") or "")


def test_endpoint_rejects_path_traversal(authed_client):
    """A junk ID with `..` or `/` must NEVER reach the storage layer."""
    for evil in (
        "FB-test/../../../etc/passwd",
        "FB-test\\..\\..\\evil",
        "P-test/../../evil",
        "FB-..",
    ):
        r = _get(authed_client, f"/api/operator/evidence-intelligence?intake_id={evil}")
        body = r.json()
        assert body.get("ok") is False, (
            f"path-traversal ID {evil!r} must be rejected before storage "
            f"lookup; got body={body!r}"
        )


def test_intake_id_takes_priority_over_project_id(authed_client):
    """When both are passed, intake_id wins (it's the new, correct
    identifier). The endpoint must NOT silently pick the wrong one."""
    r = _get(
        authed_client,
        "/api/operator/evidence-intelligence"
        "?intake_id=FB-test12345678"
        "&project_id=garbage"
    )
    assert r.status_code == 200, (
        f"when intake_id is valid, the endpoint must use it even if "
        f"project_id is bogus. Got {r.status_code}: {r.text[:300]}"
    )
