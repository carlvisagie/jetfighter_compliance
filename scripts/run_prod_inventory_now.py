#!/usr/bin/env python3
"""Production inventory reconciliation — auth via scripts.lib.ops_client (.ops_env OPS_PASSWORD)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

import httpx  # noqa: E402

from scripts.lib.ops_client import OpsAuthError, authenticate_production  # noqa: E402

# Production-Is-The-Only-Truth contract: no --target / --env / --local allowed.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _prod_only import reject_target_flag  # noqa: E402
reject_target_flag()

BASE = os.environ.get("PROD_BASE_URL", "https://compliance.keepyourcontracts.com")


def main() -> int:
    result: dict = {"base_url": BASE, "endpoints": {}, "counts": {}, "disagreements": [], "ok": False}

    client = None
    headers: dict = {}
    try:
        client, headers, diag = authenticate_production(verify_deploy=True)
        result["auth_diagnostic"] = diag.as_dict()
    except OpsAuthError as exc:
        result["auth_diagnostic"] = exc.diagnostic.as_dict()
        result["error"] = exc.reason
        # Still try unauthenticated public endpoints
        with httpx.Client(base_url=BASE, timeout=90) as pub:
            for path in ("/api/public/build-info", "/api/ops/boot-status", "/health/ready"):
                r = pub.get(path)
                result["endpoints"][path] = {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:200]}
        print(json.dumps(result, indent=2))
        return 1

    def get(path: str):
        return client.get(path, headers=headers)

    # All inventory endpoints
    diag_r = get("/api/operator/intake/diagnostics")
    scan_r = get("/api/operator/intake/raw-disk-scan")
    live_r = get("/api/ops/boot-status/live")
    boot_r = get("/api/ops/boot-status")
    auth_r = get("/api/ops/auth-check")

    result["endpoints"]["/api/operator/intake/diagnostics"] = {
        "status": diag_r.status_code,
        "body": diag_r.json() if diag_r.status_code == 200 else diag_r.text[:300],
    }
    result["endpoints"]["/api/operator/intake/raw-disk-scan"] = {
        "status": scan_r.status_code,
        "body": scan_r.json() if scan_r.status_code == 200 else scan_r.text[:300],
    }
    result["endpoints"]["/api/ops/boot-status/live"] = {
        "status": live_r.status_code,
        "body": live_r.json() if live_r.status_code == 200 else live_r.text[:300],
    }
    result["endpoints"]["/api/ops/boot-status"] = {
        "status": boot_r.status_code,
        "body": boot_r.json() if boot_r.status_code == 200 else boot_r.text[:300],
    }
    result["endpoints"]["/api/ops/auth-check"] = {
        "status": auth_r.status_code,
        "body": auth_r.json() if auth_r.status_code == 200 else auth_r.text[:300],
    }

    if diag_r.status_code != 200:
        print(json.dumps(result, indent=2))
        return 1

    db = diag_r.json()
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

    if scan_r.status_code == 200:
        sb = scan_r.json()
        counts["raw_disk_scan.intake_directories"] = int(sb.get("intake_directories") or 0)
        counts["raw_disk_scan.upload_files"] = int(sb.get("upload_files") or 0)

    if live_r.status_code == 200:
        lb = live_r.json()
        counts["live_boot.intake_directories"] = int(lb.get("intake_directories") or 0)
        counts["live_boot.upload_files"] = int(lb.get("upload_files") or 0)
        counts["live_boot.queue_depth"] = int(lb.get("queue_depth") or 0)
        counts["live_boot.live_scan_status"] = lb.get("live_scan_status")
        counts["live_boot.status"] = lb.get("status")

    # Boot snapshot (cached) for mismatch detection
    if boot_r.status_code == 200:
        for e in boot_r.json().get("entries") or []:
            if e.get("component") == "intake_retention":
                counts["boot_snapshot.intake_retention_detail"] = e.get("detail")

    result["counts"] = counts
    result["inventory_agreement"] = db.get("inventory_agreement")

    disagreements: list[dict] = []
    dir_keys = [
        "inventory.intake_directories",
        "retention_scan.intake_directories",
        "diagnostics.intake_directories_found",
        "raw_disk_scan.intake_directories",
        "live_boot.intake_directories",
    ]
    dir_vals = {k: counts[k] for k in dir_keys if k in counts}
    if len(set(dir_vals.values())) > 1:
        disagreements.append({"field": "intake_directories", "values": dir_vals, "cause_endpoint": _first_divergent(dir_vals)})

    file_keys = [
        "inventory.upload_files",
        "retention_scan.upload_files",
        "diagnostics.upload_files_on_disk",
        "raw_disk_scan.upload_files",
        "live_boot.upload_files",
    ]
    file_vals = {k: counts[k] for k in file_keys if k in counts}
    if len(set(file_vals.values())) > 1:
        disagreements.append({"field": "upload_files", "values": file_vals, "cause_endpoint": _first_divergent(file_vals)})

    qd = counts.get("queue_depth")
    pr = counts.get("inventory.pending_review_count")
    if qd is not None and pr is not None and qd != pr:
        disagreements.append(
            {
                "field": "queue_depth_vs_pending_review",
                "queue_depth": qd,
                "pending_review_count": pr,
                "cause_endpoint": "/api/operator/intake/diagnostics vs services/intake/queue.py get_operator_review_queue",
            }
        )

    lss = counts.get("live_scan_status")
    if lss and lss != "healthy":
        disagreements.append({"field": "live_scan_status", "value": lss, "cause_endpoint": "/api/operator/intake/diagnostics"})

    result["disagreements"] = disagreements
    result["ok"] = len(disagreements) == 0 and lss == "healthy"

    if client:
        client.close()
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def _first_divergent(vals: dict) -> str:
    if not vals:
        return "unknown"
    canonical = next(iter(vals.values()))
    for k, v in vals.items():
        if v != canonical:
            return k
    return "none"


if __name__ == "__main__":
    sys.exit(main())
