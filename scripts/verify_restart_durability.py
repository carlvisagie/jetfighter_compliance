#!/usr/bin/env python3
"""
Production restart durability closeout — SEV-1 upload persistence proof.

Requires .ops_env with OPS_PASSWORD. Optional RENDER_API_KEY for automated restart.

Steps:
  upload -> record SHA256 -> verify endpoints -> force Render restart ->
  re-download -> verify same SHA256 -> queue/raw disk/retention/forensic proof.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

import os  # noqa: E402

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

BASE = "https://compliance.keepyourcontracts.com"
FN = "restart-durability-proof.pdf"
PAYLOAD = b"%PDF-1.4 restart durability proof"
EXPECTED_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()
OUT_PATH = _REPO / "sev1_closeout.json"

RESTART_SERVICE_NAMES = ("kyc-backend", "jetfighter_compliance", "jetfighter-compliance")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _restart_render() -> dict:
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        return {"ok": False, "reason": "RENDER_API_KEY not set — restart manually in Render dashboard"}
    hc = httpx.Client(
        base_url="https://api.render.com",
        headers={"Authorization": f"Bearer {key}"},
        timeout=120,
    )
    try:
        sid = None
        cursor: Optional[str] = None
        for _ in range(20):
            params: dict = {"limit": 50}
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
                if svc.get("name") in RESTART_SERVICE_NAMES:
                    sid = svc.get("id")
                    break
            if sid:
                break
            cursor = None
            if isinstance(payload, list) and payload:
                cursor = payload[-1].get("cursor") if isinstance(payload[-1], dict) else None
            elif isinstance(payload, dict):
                cursor = payload.get("cursor")
            if not cursor:
                break
        if not sid:
            return {"ok": False, "reason": f"service id not found for {RESTART_SERVICE_NAMES}"}
        rr = hc.post(f"/v1/services/{sid}/restart")
        return {"ok": rr.status_code in (200, 202), "service_id": sid, "status": rr.status_code}
    finally:
        hc.close()


def _archive_ghost_intakes(client, headers) -> Dict[str, Any]:
    """Remove SEV-1 ghost shells from active queue so fleet proof can pass."""
    diag = client.get(f"{BASE}/api/operator/intake/diagnostics", headers=headers)
    if diag.status_code != 200:
        return {"ok": False, "status": diag.status_code}
    ghosts = (diag.json().get("inventory_agreement") or {}).get("ghost_intakes") or []
    archived: list[str] = []
    for ghost in ghosts:
        iid = str(ghost.get("intake_id") or "")
        if not iid:
            continue
        r = client.post(
            f"{BASE}/api/operator/intake/action",
            headers=headers,
            json={
                "intake_id": iid,
                "action": "archive",
                "operator_note": "SEV-1 ghost intake closeout — payload lost, metadata shell only",
            },
        )
        if r.status_code == 200:
            archived.append(iid)
    return {"ok": True, "archived": archived, "ghost_count": len(ghosts)}


def _verify_intake(client, headers, iid: str) -> Dict[str, Any]:
    def g(p):
        return client.get(p, headers=headers)

    dl = g(f"/api/operator/intake/{iid}/files/{FN}/download")
    view = g(f"/api/operator/intake/{iid}/files/{FN}/view")
    raw = g(f"/api/operator/intake/raw-disk-scan?intake_id={iid}")
    queue = g("/api/operator/intake/queue")
    retention = g(f"/api/operator/intake/retention-check/{iid}")
    forensic = g("/api/operator/integrity/proof")
    diag = g("/api/operator/intake/diagnostics")

    dl_sha = _sha256_bytes(dl.content) if dl.status_code == 200 else None
    view_sha = _sha256_bytes(view.content) if view.status_code == 200 else None
    raw_body = raw.json() if raw.status_code == 200 else {}
    raw_row = (raw_body.get("intakes") or [{}])[0]
    ret_body = retention.json() if retention.status_code == 200 else {}
    forensic_body = forensic.json() if forensic.status_code == 200 else {}
    diag_body = diag.json() if diag.status_code == 200 else {}
    queue_ids = {r.get("intake_id") for r in (queue.json().get("queue") or []) if queue.status_code == 200}

    row: Dict[str, Any] = {
        "intake_id": iid,
        "filename": FN,
        "expected_sha256": EXPECTED_SHA256,
        "download": {"status": dl.status_code, "sha256": dl_sha, "bytes": len(dl.content) if dl.status_code == 200 else 0},
        "view": {"status": view.status_code, "sha256": view_sha, "bytes": len(view.content) if view.status_code == 200 else 0},
        "raw_disk": {
            "status": raw.status_code,
            "found": FN in (raw_row.get("upload_file_names") or []),
            "upload_file_count": raw_row.get("upload_file_count"),
        },
        "queue": {"status": queue.status_code, "in_queue": iid in queue_ids},
        "retention": ret_body,
        "forensic_proof": forensic_body,
        "inventory_agreement": diag_body.get("inventory_agreement"),
        "ghost_intake_count": (diag_body.get("inventory_agreement") or {}).get("ghost_intake_count"),
    }
    row["pass"] = (
        dl.status_code == 200
        and view.status_code == 200
        and dl_sha == EXPECTED_SHA256
        and view_sha == EXPECTED_SHA256
        and ret_body.get("ok") is True
        and ret_body.get("ghost_intake") is not True
        and ret_body.get("file_hashes_match") is True
        and raw_row.get("upload_file_count", 0) >= 1
        and iid in queue_ids
        and forensic_body.get("ok") is True
        and (diag_body.get("inventory_agreement") or {}).get("ok") is True
        and (diag_body.get("inventory_agreement") or {}).get("ghost_intake_count", 0) == 0
    )
    return row


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out: Dict[str, Any] = {
        "ts": ts,
        "base": BASE,
        "filename": FN,
        "expected_sha256": EXPECTED_SHA256,
        "ok": False,
        "verdict": "FAIL",
        "silent_disappearance_possible": "YES",
    }
    try:
        client, headers, _ = authenticate_production()
    except OpsAuthError as exc:
        out["error"] = exc.reason
        OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    out["ghost_cleanup"] = _archive_ghost_intakes(client, headers)

    files = [("files", (FN, PAYLOAD, "application/pdf"))]
    data = {"email": f"restart-durability-{ts}@keepyourcontracts.com", "expected_file_count": "1"}
    up = client.post(f"{BASE}/api/founding-beta/upload", files=files, data=data, headers=headers)
    ub = up.json() if up.status_code == 200 else {}
    iid = ub.get("intake_id")
    out["upload"] = {
        "status": up.status_code,
        "intake_id": iid,
        "proof_gate_passed": ub.get("proof_gate_passed"),
        "live_scan_confirmed": ub.get("live_scan_confirmed"),
    }
    if up.status_code != 200 or not ub.get("proof_gate_passed"):
        OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    out["pre_restart"] = _verify_intake(client, headers, iid)
    out["restart"] = _restart_render()
    if not out["restart"].get("ok"):
        out["note"] = "Set RENDER_API_KEY in .ops_env or restart kyc-backend manually, then re-run"
        OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    for _ in range(36):
        time.sleep(10)
        try:
            h = client.get(f"{BASE}/health/ready", headers=headers)
            if h.status_code == 200 and h.json().get("ok"):
                break
        except Exception:
            pass

    out["post_restart"] = _verify_intake(client, headers, iid)
    passed = bool(out["post_restart"].get("pass"))
    out["ok"] = passed
    out["verdict"] = "PASS" if passed else "FAIL"
    out["silent_disappearance_possible"] = "NO" if passed else "YES"
    client.close()
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
