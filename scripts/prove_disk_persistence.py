"""Disk-persistence proof: pre-probe, restart, post-probe — confirm marker survives.

The organism's `disk_persistence_check` flips between three states:

  pending_first_restart  → AMBER  (just-deployed; marker has not yet survived a restart)
  verified_persistent    → INFO   (marker present and older than this process — proof)
  ephemeral_lost         → RED    (marker disappeared between boots — SEV-1)

This script reads the pre-state, restarts the Render service, waits for the new
boot to become ready, and re-reads the state. PASS only if the new state is
`verified_persistent` AND the marker_birth_utc is unchanged.

Requires `.ops_env` with `OPS_PASSWORD` (session login) and `RENDER_API_KEY`
(for the restart API call).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_ops_env = _REPO / ".ops_env"
if _ops_env.is_file():
    for line in _ops_env.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and not os.environ.get(k, "").strip():
            os.environ[k] = v

import httpx  # noqa: E402

from scripts.lib.ops_client import OpsAuthError, authenticate_production  # noqa: E402

RENDER_SERVICE_NAMES = ("kyc-backend", "jetfighter_compliance", "jetfighter-compliance")
RESTART_WAIT_S = 360  # six minutes — enough for a slow Render redeploy
POLL_INTERVAL_S = 10


def _read_persistence(client, headers) -> Dict[str, Any]:
    r = client.get("/api/operator/organism/state", headers=headers)
    if r.status_code != 200:
        return {"error": f"organism/state returned {r.status_code}"}
    body = r.json()
    return {
        "state": body.get("disk_persistence_state"),
        "verified": body.get("disk_persistence_verified"),
        "git_commit": (body.get("git_commit") or "")[:7],
        "marker_birth_utc": (body.get("disk_persistence") or {}).get("marker_birth_utc"),
        "marker_path": (body.get("disk_persistence") or {}).get("marker_path"),
    }


def _restart_render() -> Dict[str, Any]:
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        return {"ok": False, "reason": "RENDER_API_KEY missing from .ops_env"}
    hc = httpx.Client(
        base_url="https://api.render.com",
        headers={"Authorization": f"Bearer {key}"},
        timeout=120,
    )
    try:
        sid: Optional[str] = None
        cursor: Optional[str] = None
        for _ in range(20):
            params: Dict[str, Any] = {"limit": 50}
            if cursor:
                params["cursor"] = cursor
            sv = hc.get("/v1/services", params=params)
            if sv.status_code != 200:
                return {"ok": False, "list_status": sv.status_code, "body": sv.text[:300]}
            payload = sv.json()
            rows = payload if isinstance(payload, list) else [payload]
            for row in rows:
                svc = row.get("service") if isinstance(row, dict) else None
                if not isinstance(svc, dict):
                    continue
                if svc.get("name") in RENDER_SERVICE_NAMES:
                    sid = svc.get("id")
                    break
            if sid:
                break
            cursor = None
            if isinstance(payload, list) and payload:
                last = payload[-1]
                cursor = last.get("cursor") if isinstance(last, dict) else None
            elif isinstance(payload, dict):
                cursor = payload.get("cursor")
            if not cursor:
                break
        if not sid:
            return {"ok": False, "reason": f"service id not found for {RENDER_SERVICE_NAMES}"}
        rr = hc.post(f"/v1/services/{sid}/restart")
        return {
            "ok": rr.status_code in (200, 202),
            "service_id": sid,
            "restart_status": rr.status_code,
            "body": rr.text[:200],
        }
    finally:
        hc.close()


def _wait_for_new_boot(client, headers, pre_commit: str, pre_marker_birth_utc: str) -> Dict[str, Any]:
    """Return when /healthz responds AND organism reports a new process."""
    deadline = time.monotonic() + RESTART_WAIT_S
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_S)
        try:
            h = client.get("/healthz")
            if h.status_code != 200:
                continue
            now = _read_persistence(client, headers)
            if "error" in now:
                continue
            # New process iff the in-process disk_persistence cache reset.
            # The marker_birth_utc should match the same disk (durable) but the
            # process is a new one — we detect that via a fresh probe being run.
            # The simplest signal: organism/state responds and verified=True OR
            # the state changed off "pending_first_restart".
            if now.get("state") in ("verified_persistent", "ephemeral_lost", "write_failed"):
                return {"ready": True, **now}
        except Exception:
            continue
    return {"ready": False, "reason": f"timed out after {RESTART_WAIT_S}s"}


def main() -> int:
    print("=== Disk persistence proof ===")
    try:
        client, headers, _diag = authenticate_production()
    except OpsAuthError as exc:
        print("AUTH FAIL:", exc.reason)
        return 1

    pre = _read_persistence(client, headers)
    print("PRE  state            :", pre.get("state"))
    print("PRE  verified         :", pre.get("verified"))
    print("PRE  marker_birth_utc :", pre.get("marker_birth_utc"))
    print("PRE  git_commit       :", pre.get("git_commit"))

    if pre.get("state") == "verified_persistent" and pre.get("verified"):
        print()
        print("ALREADY VERIFIED — no restart needed.")
        print("Verdict: PASS (idempotent — disk already proven persistent)")
        return 0

    print()
    print("Triggering Render restart…")
    r = _restart_render()
    print("Restart response:", r)
    if not r.get("ok"):
        print("Verdict: FAIL — restart did not start")
        return 2

    print()
    print(f"Waiting up to {RESTART_WAIT_S}s for new boot to become ready…")
    waited = _wait_for_new_boot(client, headers, pre.get("git_commit", ""), pre.get("marker_birth_utc", ""))
    if not waited.get("ready"):
        print("Verdict: FAIL — boot never became ready:", waited.get("reason"))
        return 3

    print()
    post = _read_persistence(client, headers)
    print("POST state            :", post.get("state"))
    print("POST verified         :", post.get("verified"))
    print("POST marker_birth_utc :", post.get("marker_birth_utc"))
    print("POST git_commit       :", post.get("git_commit"))

    same_marker = (pre.get("marker_birth_utc") or "") == (post.get("marker_birth_utc") or "")
    passed = (
        post.get("state") == "verified_persistent"
        and post.get("verified") is True
        and same_marker
    )
    print()
    print("marker_birth_utc unchanged across restart:", same_marker)
    print("Verdict:", "PASS" if passed else "FAIL")
    return 0 if passed else 4


if __name__ == "__main__":
    sys.exit(main())
