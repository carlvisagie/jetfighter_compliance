"""
Guardrail: every operator endpoint MUST carry the env envelope.

Contract: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md

A request to any /api/operator/* JSON endpoint, with valid ops auth, returns
either:
  - a dict payload containing `_env` with `environment`, `trust`, `data_root`,
    `host`, `service`, `git_commit`, `server_time_utc`, `ops_api_key_configured`,
  - or any payload accompanied by an `X-Env-Envelope` HTTP header containing
    the same JSON envelope.

The env-envelope middleware in server.py is responsible for adding this.
This test exists so a future agent cannot delete the middleware without
breaking the build.
"""
from __future__ import annotations

import json

import pytest

from services import env_envelope as _env_mod


def _assert_envelope_shape(env: dict) -> None:
    required = {
        "environment",
        "trust",
        "data_root",
        "host",
        "service",
        "git_commit",
        "server_time_utc",
        "ops_api_key_configured",
    }
    missing = required - set(env.keys())
    assert not missing, f"env envelope missing keys: {missing}; got {env!r}"
    assert env["environment"] in ("production", "non-production"), env
    assert env["trust"] in ("trusted", "DO_NOT_TRUST"), env
    if env["environment"] == "production":
        assert env["trust"] == "trusted"
    else:
        assert env["trust"] == "DO_NOT_TRUST"


def test_env_envelope_pure_helper_shape():
    env = _env_mod.env_envelope()
    _assert_envelope_shape(env)


def test_pytest_session_is_classified_non_production():
    """Inside the test session we must NEVER classify as production."""
    env = _env_mod.env_envelope()
    assert env["environment"] == "non-production", (
        "Pytest classified itself as PRODUCTION — that is a contract violation. "
        "Production requires ENVIRONMENT=production + /var/data data root + "
        "OPS_API_KEY. Test environment must not satisfy all three."
    )
    assert env["trust"] == "DO_NOT_TRUST"


def test_environment_label_endpoint_returns_alarm_in_tests(client):
    r = client.get("/api/operator/environment-label")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["level"] == "alarm", body
    assert body["label"] == "NON-PRODUCTION", body
    _assert_envelope_shape(body["_env"])


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/operator/cockpit",
        "/api/operator/storage-status",
        "/api/operator/organism/state",
        "/api/operator/vio/overview",
        "/api/operator/telemetry-status",
    ],
)
def test_operator_endpoints_carry_env_envelope_in_body_or_header(client, endpoint):
    r = client.get(endpoint)
    # Endpoint may legitimately 4xx/5xx in test config (no data) — but if it returns
    # any JSON, that JSON must carry provenance.
    if not r.headers.get("content-type", "").lower().startswith("application/json"):
        # non-JSON response (e.g. 304 / file) — header envelope is enough
        assert "X-Env-Envelope" in r.headers, (
            f"{endpoint}: non-JSON response missing X-Env-Envelope header"
        )
        env = json.loads(r.headers["X-Env-Envelope"])
        _assert_envelope_shape(env)
        return

    assert "X-Env-Envelope" in r.headers, (
        f"{endpoint}: response missing X-Env-Envelope header"
    )
    header_env = json.loads(r.headers["X-Env-Envelope"])
    _assert_envelope_shape(header_env)

    body = r.json()
    if isinstance(body, dict):
        assert "_env" in body, f"{endpoint}: dict body missing `_env` key"
        _assert_envelope_shape(body["_env"])
        assert body["_env"]["environment"] == header_env["environment"]


def test_anonymous_caller_does_not_leak_env_envelope_on_blocked_routes(anon_client):
    """
    The env envelope is operator-protected. An unauthenticated caller hitting
    a protected route must NOT receive a usable envelope (auth blocks the
    route before middleware would inject anything).
    """
    r = anon_client.get("/api/operator/storage-status")
    assert r.status_code in (302, 401, 403), r.status_code
