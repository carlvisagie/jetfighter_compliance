"""
Shared operator HTTP client — single auth contract for all production scripts.

Auth modes (exactly one):
  1. OPS_API_KEY  → header X-Ops-Key
  2. OPS_PASSWORD → POST /api/ops/login → cookie kyc_ops_session

No Authorization Bearer, X-OPS-PASSWORD, or custom headers.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

# Allow `from scripts.lib.ops_client import ...` when repo root is on sys.path.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ops_auth import OPS_API_KEY_HEADER, SESSION_COOKIE, auth_contract  # noqa: E402

BRANDED_BASE_URL = "https://compliance.keepyourcontracts.com"
RENDER_BASE_URL = "https://jetfighter-compliance.onrender.com"
AUTH_PROBE_PATH = "/api/ops/auth-check"
BUILD_INFO_PATH = "/api/public/build-info"
SESSION_PROBE_PATH = "/api/ops/session"


@dataclass
class OpsAuthDiagnostic:
    base_url: str
    auth_mode_selected: Optional[str] = None
    header_name_used: Optional[str] = None
    env_ops_password_present: bool = False
    env_ops_password_length: int = 0
    env_ops_api_key_present: bool = False
    env_ops_api_key_length: int = 0
    auth_probe_endpoint: str = AUTH_PROBE_PATH
    auth_probe_status: Optional[int] = None
    auth_probe_body: Dict[str, Any] = field(default_factory=dict)
    failure_reason: Optional[str] = None
    build_info: Dict[str, Any] = field(default_factory=dict)
    deploy_parity: Dict[str, Any] = field(default_factory=dict)
    session_probe: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "auth_mode_selected": self.auth_mode_selected,
            "header_name_used": self.header_name_used,
            "env_ops_password_present": self.env_ops_password_present,
            "env_ops_password_length": self.env_ops_password_length,
            "env_ops_api_key_present": self.env_ops_api_key_present,
            "env_ops_api_key_length": self.env_ops_api_key_length,
            "auth_probe_endpoint": self.auth_probe_endpoint,
            "auth_probe_status": self.auth_probe_status,
            "auth_probe_body": self.auth_probe_body,
            "failure_reason": self.failure_reason,
            "build_info": self.build_info,
            "deploy_parity": self.deploy_parity,
            "session_probe": self.session_probe,
            "auth_contract": auth_contract(),
        }


class OpsAuthError(Exception):
    def __init__(self, reason: str, diagnostic: OpsAuthDiagnostic):
        super().__init__(reason)
        self.reason = reason
        self.diagnostic = diagnostic


def _env_secret(name: str) -> Tuple[str, bool, int]:
    raw = os.environ.get(name, "")
    val = raw.strip()
    return val, bool(val), len(val)


def select_auth_mode() -> Tuple[Optional[str], Dict[str, str]]:
    api_key, api_present, _ = _env_secret("OPS_API_KEY")
    password, pwd_present, _ = _env_secret("OPS_PASSWORD")
    if api_present:
        return "api_key", {OPS_API_KEY_HEADER: api_key}
    if pwd_present:
        return "session_cookie", {}
    return None, {}


def fetch_build_info(client: httpx.Client, base_url: str) -> Dict[str, Any]:
    r = client.get(f"{base_url.rstrip('/')}{BUILD_INFO_PATH}")
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code, "body": r.text[:300]}
    body = r.json()
    body["ok"] = True
    body["url"] = base_url
    return body


def verify_deploy_parity(client: httpx.Client) -> Dict[str, Any]:
    branded = fetch_build_info(client, BRANDED_BASE_URL)
    render = fetch_build_info(client, RENDER_BASE_URL)
    out: Dict[str, Any] = {
        "branded": branded,
        "render": render,
        "ok": False,
    }
    if not branded.get("ok") or not render.get("ok"):
        out["failure_reason"] = "build_info_unreachable"
        return out
    bc = branded.get("git_commit")
    rc = render.get("git_commit")
    out["branded_commit"] = bc
    out["render_commit"] = rc
    if bc != rc:
        out["failure_reason"] = "branded_domain_points_to_different_service"
        return out
    if bc == "unknown":
        out["failure_reason"] = "stale_deployed_commit_unknown"
        return out
    out["ok"] = True
    return out


def probe_session(client: httpx.Client, base_url: str) -> Dict[str, Any]:
    r = client.get(f"{base_url.rstrip('/')}{SESSION_PROBE_PATH}")
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code}
    return {"ok": True, **r.json()}


def authenticate_production(
    *,
    base_url: Optional[str] = None,
    verify_deploy: bool = True,
    timeout: float = 90.0,
) -> Tuple[httpx.Client, Dict[str, str], OpsAuthDiagnostic]:
    """
    Return (httpx_client, request_headers, diagnostic).
    Caller must use the same client for session auth (cookies).
    """
    base = (base_url or os.environ.get("PROD_BASE_URL") or BRANDED_BASE_URL).rstrip("/")
    diag = OpsAuthDiagnostic(base_url=base)

    pwd, diag.env_ops_password_present, diag.env_ops_password_length = _env_secret("OPS_PASSWORD")
    key, diag.env_ops_api_key_present, diag.env_ops_api_key_length = _env_secret("OPS_API_KEY")

    client = httpx.Client(base_url=base, timeout=timeout, follow_redirects=False)

    if verify_deploy:
        parity = verify_deploy_parity(client)
        diag.deploy_parity = parity
        if not parity.get("ok"):
            diag.failure_reason = parity.get("failure_reason") or "deploy_parity_failed"
            raise OpsAuthError(diag.failure_reason, diag)

    branded_info = fetch_build_info(client, base)
    diag.build_info = branded_info
    if not branded_info.get("ok"):
        diag.failure_reason = "build_info_unreachable"
        raise OpsAuthError(diag.failure_reason, diag)

    mode, headers = select_auth_mode()
    if mode is None:
        diag.failure_reason = "missing_env_var"
        raise OpsAuthError(diag.failure_reason, diag)

    diag.auth_mode_selected = mode
    diag.header_name_used = OPS_API_KEY_HEADER if mode == "api_key" else SESSION_COOKIE
    diag.session_probe = probe_session(client, base)

    if mode == "api_key":
        probe = client.get(AUTH_PROBE_PATH, headers=headers)
        diag.auth_probe_status = probe.status_code
        if probe.status_code == 200:
            diag.auth_probe_body = probe.json()
            return client, headers, diag
        if probe.status_code == 403:
            diag.failure_reason = "wrong_secret"
        elif probe.status_code == 503:
            diag.failure_reason = "server_auth_not_configured"
        else:
            diag.failure_reason = "wrong_header_contract"
        try:
            diag.auth_probe_body = probe.json()
        except Exception:
            diag.auth_probe_body = {"raw": probe.text[:300]}
        raise OpsAuthError(diag.failure_reason, diag)

    # session_cookie mode
    if not diag.session_probe.get("password_configured"):
        if diag.session_probe.get("api_key_configured"):
            diag.failure_reason = "server_password_not_configured_use_ops_api_key"
        else:
            diag.failure_reason = "server_auth_not_configured"
        raise OpsAuthError(diag.failure_reason, diag)

    login = client.post("/api/ops/login", json={"password": pwd})
    if login.status_code == 503:
        diag.failure_reason = "server_auth_not_configured"
        diag.auth_probe_status = login.status_code
        raise OpsAuthError(diag.failure_reason, diag)
    if login.status_code == 401:
        diag.failure_reason = "wrong_secret"
        diag.auth_probe_status = login.status_code
        raise OpsAuthError(diag.failure_reason, diag)
    if login.status_code != 200 or not login.json().get("ok"):
        diag.failure_reason = "wrong_header_contract"
        diag.auth_probe_status = login.status_code
        raise OpsAuthError(diag.failure_reason, diag)

    probe = client.get(AUTH_PROBE_PATH)
    diag.auth_probe_status = probe.status_code
    if probe.status_code == 200:
        diag.auth_probe_body = probe.json()
        if diag.auth_probe_body.get("auth_mode") != "session_cookie":
            diag.failure_reason = "wrong_header_contract"
            raise OpsAuthError(diag.failure_reason, diag)
        return client, {}, diag

    diag.failure_reason = "wrong_secret" if probe.status_code == 403 else "wrong_header_contract"
    try:
        diag.auth_probe_body = probe.json()
    except Exception:
        diag.auth_probe_body = {"raw": probe.text[:300]}
    raise OpsAuthError(diag.failure_reason, diag)
