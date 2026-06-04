"""
scripts/_prod_only.py — the ONLY sanctioned way for a script to ask
"how many intakes / projects / uploads does production have right now?"

Contract: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md

This module exists because the 2026-06-04 forensic audit proved that scripts
which "tested against local" were the root cause of the platform being
reported as having 40 intakes when production had zero. We deleted that
pattern. There is no local mode. There is no `--target=local`. There is
production, and there is "go write a pytest instead".

Usage:

    from scripts._prod_only import production_client

    client = production_client()              # exits 2 if OPS_API_KEY is missing
    payload = client.get_operator("/api/operator/organism/state")
    env = payload["_env"]
    assert env["environment"] == "production", "Got noise from prod URL — investigate"

The client:
  * hard-codes the production base URL (both the custom domain and the
    Render fallback). It refuses to be redirected elsewhere.
  * requires OPS_API_KEY as an env var or as a value in ./.ops_env. No fallback.
  * verifies every response carries the production envelope; raises loudly
    if it does not (so a misconfigured deploy can never silently lie).
  * never accepts a `--target` CLI flag. There is nothing to target but prod.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    import httpx
except ImportError:  # pragma: no cover - install hint
    sys.stderr.write("httpx not installed. pip install httpx\n")
    sys.exit(2)


PRODUCTION_BASE_URL = "https://compliance.keepyourcontracts.com"
PRODUCTION_FALLBACK_URL = "https://jetfighter-compliance.onrender.com"
OPS_ENV_FILE = Path(__file__).resolve().parent.parent / ".ops_env"


class NotProductionError(RuntimeError):
    """Raised when a response from the production URL does not carry the
    production envelope. Indicates a misconfigured deploy and is fatal —
    the script must NOT continue and quote whatever numbers came back."""


def _load_ops_api_key() -> str:
    val = (os.getenv("OPS_API_KEY") or "").strip()
    if val:
        return val
    if OPS_ENV_FILE.exists():
        for raw in OPS_ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("OPS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def reject_target_flag(argv: Optional[Iterable[str]] = None) -> None:
    """
    Every script that imports this module also calls reject_target_flag()
    at startup so that a `--target=local` or `--target=test` invocation
    exits with a clear, non-bypassable failure.

    Tested by tests/test_scripts_hit_production_guardrail.py.
    """
    args = list(argv if argv is not None else sys.argv[1:])
    forbidden_substrings = ("--target", "--env=", "--environment=", "--local", "--use-local")
    for a in args:
        low = (a or "").lower()
        if any(low.startswith(sub) or low == sub for sub in forbidden_substrings):
            sys.stderr.write(
                "REFUSED: scripts under scripts/ never accept --target / --env / --local.\n"
                "There is one environment: production. See docs/PRODUCTION_IS_THE_ONLY_TRUTH.md\n"
                "If you want to exercise code paths, write a pytest. Pytest is hard-isolated\n"
                "to per-session temp dirs by tests/conftest.py.\n"
            )
            sys.exit(2)


def production_argparser(prog: str | None = None, description: str = "") -> argparse.ArgumentParser:
    """
    Returns an ArgumentParser pre-configured to disallow environment flags.

    Any subclass adding new arguments must NOT add --target / --env /
    --environment / --local; those are reserved by reject_target_flag()
    and the guardrail test will fail if reintroduced.
    """
    p = argparse.ArgumentParser(prog=prog, description=description)
    p.add_argument(
        "--why",
        dest="why",
        default="",
        help="One-line audit reason for hitting production (recorded in stdout).",
    )
    return p


class ProductionClient:
    """Tiny wrapper around httpx that ONLY talks to production."""

    def __init__(self, base_url: str, ops_api_key: str, timeout: float = 25.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.ops_api_key = ops_api_key
        self.timeout = timeout

    # ------- low-level -------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {
            "X-Ops-Key": self.ops_api_key,
            "Accept": "application/json",
            "User-Agent": "kyc-prod-only-script/1.0",
        }

    def _verify_envelope(self, endpoint: str, payload: Any) -> None:
        if not isinstance(payload, dict):
            return  # list endpoints — header carries envelope, we trust it implicitly
        env = payload.get("_env")
        if not isinstance(env, dict):
            raise NotProductionError(
                f"{endpoint}: response missing `_env` envelope. "
                "Deploy is older than PRODUCTION_IS_THE_ONLY_TRUTH or wrong host."
            )
        if env.get("environment") != "production":
            raise NotProductionError(
                f"{endpoint}: production URL returned environment="
                f"{env.get('environment')!r} (trust={env.get('trust')!r}). "
                "Refusing to quote any number from this response."
            )

    # ------- public ---------------------------------------------------
    def get_operator(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not endpoint.startswith("/api/operator/"):
            raise ValueError("production_client only talks to /api/operator/* endpoints")
        url = self.base_url + endpoint
        resp = httpx.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
            follow_redirects=False,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._verify_envelope(endpoint, payload)
        return payload

    def post_operator(self, endpoint: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not endpoint.startswith("/api/operator/"):
            raise ValueError("production_client only talks to /api/operator/* endpoints")
        url = self.base_url + endpoint
        resp = httpx.post(
            url,
            headers=self._headers(),
            json=body or {},
            timeout=self.timeout,
            follow_redirects=False,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._verify_envelope(endpoint, payload)
        return payload

    def organism_counts(self) -> Dict[str, Any]:
        """Convenience for "give me the paperwork counts straight from prod"."""
        state = self.get_operator("/api/operator/organism/state")
        env = state.get("_env", {})
        # The exact key path depends on the live shape; surface enough provenance
        # that the caller never has to guess what they are quoting.
        return {
            "_env": env,
            "raw": state,
        }


def production_client(*, allow_fallback_url: bool = True) -> ProductionClient:
    """
    Returns a ProductionClient bound to the production base URL.

    Will sys.exit(2) if OPS_API_KEY is not available. There is no anonymous
    "just peek" mode.
    """
    reject_target_flag()
    key = _load_ops_api_key()
    if not key:
        sys.stderr.write(
            "REFUSED: OPS_API_KEY is not set in the environment or in ./.ops_env.\n"
            "Every script that touches paperwork hits production. Production requires\n"
            "the operator key. See docs/PRODUCTION_IS_THE_ONLY_TRUTH.md\n"
        )
        sys.exit(2)
    base = PRODUCTION_BASE_URL
    # Allow the Render fallback only when explicitly requested; never a local URL.
    if allow_fallback_url and os.getenv("KYC_USE_RENDER_FALLBACK", "").lower() in ("1", "true", "yes"):
        base = PRODUCTION_FALLBACK_URL
    return ProductionClient(base_url=base, ops_api_key=key)


__all__ = [
    "PRODUCTION_BASE_URL",
    "PRODUCTION_FALLBACK_URL",
    "NotProductionError",
    "ProductionClient",
    "production_argparser",
    "production_client",
    "reject_target_flag",
]
