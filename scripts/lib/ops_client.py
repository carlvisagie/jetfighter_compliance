"""
Shared operator HTTP client — single auth contract for all production scripts.

Scripts (only):
  OPS_PASSWORD → POST /api/ops/login → cookie kyc_ops_session

Local creds: repo-root `.ops_env` (gitignored) via load_local_ops_env().

No OPS_API_KEY, Authorization Bearer, X-OPS-PASSWORD, or custom headers in scripts.
Server may still accept X-Ops-Key for other clients; scripts do not use it.
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

from services.ops_auth import SESSION_COOKIE, auth_contract  # noqa: E402

BRANDED_BASE_URL = "https://compliance.keepyourcontracts.com"
RENDER_BASE_URL = "https://jetfighter-compliance.onrender.com"
AUTH_PROBE_PATH = "/api/ops/auth-check"
BUILD_INFO_PATH = "/api/public/build-info"
SESSION_PROBE_PATH = "/api/ops/session"
OPS_ENV_FILENAME = ".ops_env"


@dataclass
class OpsAuthDiagnostic:
    base_url: str
    auth_mode_selected: Optional[str] = None
    header_name_used: Optional[str] = None
    env_ops_password_present: bool = False
    env_ops_password_length: int = 0
    env_ops_api_key_present: bool = False
    env_ops_api_key_length: int = 0
    ops_env_file: Optional[str] = None
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
            "ops_env_file": self.ops_env_file,
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


def load_local_ops_env() -> Optional[Path]:
    """Load OPS_PASSWORD and PROD_BASE_URL from repo-root `.ops_env` only."""
    path = _REPO_ROOT / OPS_ENV_FILENAME
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ("OPS_PASSWORD", "PROD_BASE_URL") and v and not os.environ.get(k, "").strip():
            os.environ[k] = v
    return path


def _resolve_script_password(diag: OpsAuthDiagnostic) -> str:
    """Scripts: OPS_PASSWORD session only; fail if OPS_API_KEY is set."""
    _, diag.env_ops_api_key_present, diag.env_ops_api_key_length = _env_secret("OPS_API_KEY")
    if diag.env_ops_api_key_present:
        diag.failure_reason = "scripts_use_ops_password_only"
        raise OpsAuthError(diag.failure_reason, diag)

    pwd, diag.env_ops_password_present, diag.env_ops_password_length = _env_secret("OPS_PASSWORD")
    if not diag.env_ops_password_present:
        diag.failure_reason = "missing_env_var"
        raise OpsAuthError(diag.failure_reason, diag)
    return pwd


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
    Scripts use session cookies only; request_headers is always {}.
    """
    base = (base_url or os.environ.get("PROD_BASE_URL") or BRANDED_BASE_URL).rstrip("/")
    ops_env = load_local_ops_env()
    diag = OpsAuthDiagnostic(base_url=base)
    if ops_env is not None:
        diag.ops_env_file = str(ops_env)

    pwd = _resolve_script_password(diag)
    diag.auth_mode_selected = "session_cookie"
    diag.header_name_used = SESSION_COOKIE

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

    diag.session_probe = probe_session(client, base)

    if not diag.session_probe.get("password_configured"):
        diag.failure_reason = "server_password_not_configured"
        raise OpsAuthError(diag.failure_reason, diag)

    login = client.post("/api/ops/login", json={"password": pwd})
    if login.status_code == 503:
        diag.failure_reason = "server_auth_not_configured"
        diag.auth_probe_status = login.status_code
        raise OpsAuthError(diag.failure_reason, diag)
    if login.status_code == 401:
        diag.failure_reason = "login_rejected"
        diag.auth_probe_status = login.status_code
        try:
            diag.auth_probe_body = login.json()
        except Exception:
            diag.auth_probe_body = {"raw": login.text[:300]}
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
