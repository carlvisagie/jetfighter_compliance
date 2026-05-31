#!/usr/bin/env python3
"""Production inventory agreement verifier — exits non-zero on any count mismatch."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.lib.ops_client import OpsAuthError, authenticate_production  # noqa: E402


def main() -> int:
    out: dict = {"ok": False}
    client = None
    try:
        client, headers, auth_diag = authenticate_production()
        out["auth_diagnostic"] = auth_diag.as_dict()
    except OpsAuthError as exc:
        out["auth_diagnostic"] = exc.diagnostic.as_dict()
        out["error"] = exc.reason
        print(json.dumps(out, indent=2))
        return 1

    try:
        diag = client.get("/api/operator/intake/diagnostics", headers=headers)
        live = client.get("/api/ops/boot-status/live", headers=headers)
        scan = client.get("/api/operator/intake/raw-disk-scan", headers=headers)

        out["diagnostics_status"] = diag.status_code
        out["live_boot_status"] = live.status_code
        out["raw_scan_status"] = scan.status_code

        if diag.status_code != 200:
            out["error"] = "diagnostics_unavailable"
            print(json.dumps(out, indent=2))
            return 1

        db = diag.json()
        d = db.get("diagnostics") or {}
        inv = d.get("inventory") or {}
        rs = d.get("retention_scan") or {}

        counts = {
            "inventory.intake_directories": int(inv.get("intake_directories") or 0),
            "inventory.upload_files": int(inv.get("upload_files") or 0),
            "inventory.pending_review_count": int(inv.get("pending_review_count") or 0),
            "retention_scan.intake_directories": int(rs.get("intake_directories") or 0),
            "retention_scan.upload_files": int(rs.get("upload_files") or 0),
            "diagnostics.intake_directories_found": int(d.get("intake_directories_found") or 0),
            "diagnostics.upload_files_on_disk": int(d.get("upload_files_on_disk") or 0),
            "diagnostics.pending_review_count": int(d.get("pending_review_count") or 0),
            "queue_depth": int(db.get("queue_depth") or 0),
            "live_scan_status": db.get("live_scan_status"),
        }

        if live.status_code == 200:
            lb = live.json()
            counts["live_boot.intake_directories"] = int(lb.get("intake_directories") or 0)
            counts["live_boot.upload_files"] = int(lb.get("upload_files") or 0)
            counts["live_boot.queue_depth"] = int(lb.get("queue_depth") or 0)
            counts["live_boot.live_scan_status"] = lb.get("live_scan_status")
            counts["live_boot.status"] = lb.get("status")

        if scan.status_code == 200:
            sb = scan.json()
            counts["raw_disk_scan.intake_directories"] = int(sb.get("intake_directories") or 0)
            counts["raw_disk_scan.upload_files"] = int(sb.get("upload_files") or 0)

        out["inventory_agreement"] = db.get("inventory_agreement")
        out["ghost_intake_count"] = (db.get("inventory_agreement") or {}).get("ghost_intake_count")
        out["ghost_intakes"] = (db.get("inventory_agreement") or {}).get("ghost_intakes")

        disagreements: list[dict] = []
        dir_values = {
            k: v
            for k, v in counts.items()
            if k.endswith("intake_directories") or k.endswith("intake_directories_found")
        }
        file_values = {
            k: v for k, v in counts.items() if k.endswith("upload_files") or k.endswith("upload_files_on_disk")
        }

        if dir_values and len(set(dir_values.values())) > 1:
            disagreements.append({"field": "intake_directories", "values": dir_values})
        if file_values and len(set(file_values.values())) > 1:
            disagreements.append({"field": "upload_files", "values": file_values})

        pending = int(inv.get("pending_review_count") or 0)
        qd = int(db.get("queue_depth") or 0)
        if pending != qd:
            disagreements.append(
                {"field": "pending_review_count", "inventory": pending, "queue_depth": qd}
            )

        live_status = db.get("live_scan_status")
        ghost_count = int((db.get("inventory_agreement") or {}).get("ghost_intake_count") or 0)
        if ghost_count > 0:
            disagreements.append({"field": "ghost_intakes", "count": ghost_count})

        out["counts"] = counts
        out["inventory_agreement"] = db.get("inventory_agreement")
        out["disagreements"] = disagreements
        out["ok"] = len(disagreements) == 0 and live_status == "healthy" and ghost_count == 0
    finally:
        if client is not None:
            client.close()

    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
