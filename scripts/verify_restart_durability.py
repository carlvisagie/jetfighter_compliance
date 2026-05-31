#!/usr/bin/env python3
"""
Production restart durability proof.

Requires .ops_env with OPS_PASSWORD. Optional RENDER_API_KEY for automated restart.

Steps: upload -> verify -> restart -> wait -> verify same intake still on disk.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

import httpx  # noqa: E402

from scripts.lib.ops_client import OpsAuthError, authenticate_production  # noqa: E402

BASE = "https://compliance.keepyourcontracts.com"
FN = "restart-durability-proof.pdf"


def _restart_render() -> dict:
    import os

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
                if svc.get("name") == "kyc-backend":
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
            return {"ok": False, "reason": "service id not found for kyc-backend"}
        rr = hc.post(f"/v1/services/{sid}/restart")
        return {"ok": rr.status_code in (200, 202), "service_id": sid, "status": rr.status_code}
    finally:
        hc.close()


def _verify_intake(client, headers, iid: str) -> dict:
    def g(p):
        return client.get(p, headers=headers)

    row = {
        "intake_id": iid,
        "filename": FN,
        "retention": g(f"/api/operator/intake/retention-check/{iid}").json(),
        "download_status": g(f"/api/operator/intake/{iid}/files/{FN}/download").status_code,
        "view_status": g(f"/api/operator/intake/{iid}/files/{FN}/view").status_code,
        "inventory": g("/api/operator/intake/diagnostics").json(),
    }
    ret = row["retention"]
    row["pass"] = (
        ret.get("ok") is True
        and ret.get("ghost_intake") is not True
        and row["download_status"] == 200
        and row["view_status"] == 200
        and ret.get("file_hashes_match") is True
    )
    return row


def main() -> int:
    out: dict = {"base": BASE, "ok": False}
    try:
        client, headers, _ = authenticate_production()
    except OpsAuthError as exc:
        out["error"] = exc.reason
        print(json.dumps(out, indent=2))
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    files = [("files", (FN, b"%PDF-1.4 restart durability proof", "application/pdf"))]
    data = {"email": f"restart-durability-{ts}@keepyourcontracts.com", "expected_file_count": "1"}
    up = client.post("/api/founding-beta/upload", files=files, data=data)
    ub = up.json() if up.status_code == 200 else {}
    iid = ub.get("intake_id")
    out["upload"] = {"status": up.status_code, "intake_id": iid, "proof_gate_passed": ub.get("proof_gate_passed")}
    if up.status_code != 200 or not ub.get("proof_gate_passed"):
        print(json.dumps(out, indent=2))
        return 1

    out["pre_restart"] = _verify_intake(client, headers, iid)
    out["restart"] = _restart_render()
    if not out["restart"].get("ok"):
        out["note"] = "Set RENDER_API_KEY in .ops_env or restart kyc-backend manually, then re-run with --skip-upload"
        print(json.dumps(out, indent=2))
        return 1

    for _ in range(36):
        time.sleep(10)
        try:
            h = client.get("/health/ready")
            if h.status_code == 200 and h.json().get("ok"):
                break
        except Exception:
            pass

    out["post_restart"] = _verify_intake(client, headers, iid)
    inv = client.get("/api/operator/intake/diagnostics", headers=headers)
    if inv.status_code == 200:
        body = inv.json()
        out["inventory_agreement"] = body.get("inventory_agreement")
        out["ghost_intake_count"] = body.get("inventory_agreement", {}).get("ghost_intake_count")
    out["ok"] = bool(out["post_restart"].get("pass"))
    out["silent_disappearance_possible"] = "NO" if out["ok"] else "YES"
    client.close()
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
