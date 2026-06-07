#!/usr/bin/env python3
"""Production forensic proof — OPS_PASSWORD via scripts.lib.ops_client (.ops_env)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.lib.ops_client import OpsAuthError, authenticate_production  # noqa: E402

# Production-Is-The-Only-Truth contract: no --target / --env / --local allowed.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _prod_only import reject_target_flag  # noqa: E402
reject_target_flag()


def main() -> int:
    out: dict = {
        "proved_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deploy_check": {},
        "steps": {},
        "ok": False,
    }
    errors: list[str] = []
    client = None

    try:
        client, headers, auth_diag = authenticate_production()
        out["auth_diagnostic"] = auth_diag.as_dict()
        out["base_url"] = auth_diag.base_url
        out["auth_mode"] = auth_diag.auth_mode_selected
    except OpsAuthError as exc:
        out["auth_diagnostic"] = exc.diagnostic.as_dict()
        out["error"] = exc.reason
        print(json.dumps(out, indent=2))
        return 1

    try:
        ready = client.get("/health/ready").json()
        out["deploy_check"]["health_ready"] = ready
        out["deploy_check"]["intake_uploads_enabled"] = ready.get("checks", {}).get("intake_uploads_enabled")
        out["deploy_check"]["durable_storage_configured"] = ready.get("checks", {}).get("durable_storage_configured")

        def get(path: str):
            return client.get(path, headers=headers)

        st = get("/api/operator/storage-status")
        out["steps"]["1_storage_status"] = {"status": st.status_code, "body": st.json() if st.status_code == 200 else st.text[:300]}
        if st.status_code != 200:
            errors.append(f"storage-status {st.status_code}")

        proof_before = get("/api/operator/integrity/proof")
        out["steps"]["2_proof_before"] = {
            "status": proof_before.status_code,
            "body": proof_before.json() if proof_before.status_code == 200 else proof_before.text[:300],
        }

        diag = get("/api/operator/founding-pilot/diagnostics")
        out["steps"]["3_diagnostics"] = {
            "status": diag.status_code,
            "body": diag.json() if diag.status_code == 200 else diag.text[:500],
        }

        files = [("files", ("prod-forensic-proof.pdf", b"%PDF-1.4 prod forensic proof", "application/pdf"))]
        data = {"email": "forensic-proof-prod@keepyourcontracts.com", "expected_file_count": "1"}
        upload = client.post("/api/founding-pilot/upload", files=files, data=data)
        upload_body = upload.json() if upload.status_code == 200 else {"error": upload.text[:500]}
        iid = upload_body.get("intake_id") if upload.status_code == 200 else None
        out["steps"]["4_upload"] = {"status": upload.status_code, "body": upload_body, "intake_id": iid}
        if upload.status_code != 200 or not iid:
            errors.append(f"upload failed {upload.status_code}")

        if iid:
            q = get("/api/operator/intake/queue")
            qbody = q.json() if q.status_code == 200 else {}
            in_queue = iid in {r.get("intake_id") for r in qbody.get("queue") or []}
            out["steps"]["5_queue"] = {"status": q.status_code, "in_queue": in_queue, "queue_depth": qbody.get("queue_depth")}
            if not in_queue:
                errors.append("intake not in queue")

            proof_after = get("/api/operator/integrity/proof")
            pbody = proof_after.json() if proof_after.status_code == 200 else {}
            out["steps"]["6_proof_after"] = {"status": proof_after.status_code, "body": pbody}
            samples = pbody.get("samples") or {}
            seen = any(iid in str(s) for s in (samples.get("verified") or []))
            if not seen and pbody.get("verified_files", 0) < 1:
                errors.append("proof does not see uploaded file")

            audit = get(f"/api/operator/intake/{iid}/audit")
            out["steps"]["7_audit"] = {
                "status": audit.status_code,
                "has_receipt": bool(audit.json().get("audit_receipt")) if audit.status_code == 200 else False,
            }

            ret = get(f"/api/operator/intake/retention-check/{iid}")
            rbody = ret.json() if ret.status_code == 200 else {}
            out["steps"]["8_retention"] = {"status": ret.status_code, "body": rbody}
            if ret.status_code != 200 or not rbody.get("file_hashes_match", False):
                errors.append("retention-check failed or hash mismatch")

            topo = get("/api/cognitive-topology")
            tbody = topo.json() if topo.status_code == 200 else {}
            up = (tbody.get("subsystems") or {}).get("upload_pipeline") or {}
            out["steps"]["9_cockpit_cote"] = {
                "status": topo.status_code,
                "pending_review": up.get("pending_review"),
                "queue_depth": up.get("queue_depth"),
                "upload_node_severity": up.get("upload_node_severity"),
                "latest_intake_id": up.get("latest_intake_id"),
            }
            if up.get("pending_review", 0) < 1 and up.get("queue_depth", 0) < 1:
                errors.append("COTE does not show pending paperwork")

        out["intake_id"] = iid
        out["errors"] = errors
        out["ok"] = len(errors) == 0
    finally:
        if client is not None:
            client.close()

    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
