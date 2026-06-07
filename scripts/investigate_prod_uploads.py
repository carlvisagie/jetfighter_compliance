#!/usr/bin/env python3
"""Read-only production upload investigation — stdout JSON only."""
from __future__ import annotations

import json
import sys
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
    out: dict = {"findings": {}}
    client = None
    try:
        client, headers, auth_diag = authenticate_production()
        out["base_url"] = auth_diag.base_url
        out["auth_ok"] = True
        out["auth_mode"] = auth_diag.auth_mode_selected
        out["auth_diagnostic"] = auth_diag.as_dict()
    except OpsAuthError as exc:
        out["base_url"] = exc.diagnostic.base_url
        out["auth_ok"] = False
        out["auth_error"] = exc.reason
        out["auth_diagnostic"] = exc.diagnostic.as_dict()
        print(json.dumps(out, indent=2))
        return 1

    try:
        def get(path: str):
            return client.get(path, headers=headers)

        out["findings"]["health_ready"] = client.get("/health/ready").json()

        storage = get("/api/operator/storage-status")
        out["findings"]["storage_status"] = (
            storage.json() if storage.status_code == 200 else {"status": storage.status_code, "body": storage.text[:300]}
        )

        diag = get("/api/operator/intake/diagnostics")
        out["findings"]["intake_diagnostics"] = (
            diag.json() if diag.status_code == 200 else {"status": diag.status_code}
        )

        queue = get("/api/operator/intake/queue?limit=100")
        qbody = queue.json() if queue.status_code == 200 else {}
        out["findings"]["queue"] = {
            "status": queue.status_code,
            "queue_depth": qbody.get("queue_depth"),
            "queue_rows_generated": qbody.get("queue_rows_generated"),
            "queue_empty_reason": qbody.get("queue_empty_reason"),
            "queue_empty_detail": qbody.get("queue_empty_detail"),
            "visibility_warning": qbody.get("visibility_warning"),
            "intake_ids_in_queue": [r.get("intake_id") for r in qbody.get("queue") or []],
            "queue_file_counts": [
                {"intake_id": r.get("intake_id"), "file_count": r.get("file_count"), "review_status": r.get("review_status")}
                for r in qbody.get("queue") or []
            ],
        }
        out["findings"]["dashboard"] = qbody.get("dashboard") or {}

        d = out["findings"].get("intake_diagnostics") or {}
        inner = d.get("diagnostics") or d
        sample_ids = list(inner.get("intake_ids_sample") or []) + list(inner.get("pending_intake_ids_sample") or [])
        seen: set[str] = set()
        intake_inventories = []
        total_files_api = 0
        for iid in sample_ids:
            if not iid or iid in seen:
                continue
            seen.add(iid)
            fl = get(f"/api/operator/intake/{iid}/files")
            if fl.status_code != 200:
                intake_inventories.append({"intake_id": iid, "files_status": fl.status_code})
                continue
            fb = fl.json()
            docs = fb.get("documents") or []
            total_files_api += len(docs)
            intake_inventories.append(
                {
                    "intake_id": iid,
                    "file_count": fb.get("file_count"),
                    "stored_filenames": [x.get("stored_filename") for x in docs],
                    "statuses": [x.get("status") for x in docs],
                }
            )
        out["findings"]["intake_file_inventories"] = intake_inventories
        out["findings"]["total_files_listed_via_api"] = total_files_api

        tel = get("/api/memory/telemetry?limit=500")
        if tel.status_code == 200:
            rows = tel.json().get("telemetry") or tel.json().get("rows") or []
            if isinstance(tel.json(), list):
                rows = tel.json()
            intake_events = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                et = str(r.get("event_type") or "")
                sub = str(r.get("subsystem") or "")
                meta = r.get("metadata") or {}
                if (
                    sub in ("intake", "founding_pilot")
                    or "upload" in et.lower()
                    or meta.get("intake_id")
                    or meta.get("founding_pilot")
                ):
                    intake_events.append(
                        {
                            "event_type": et,
                            "subsystem": sub,
                            "message": (r.get("message") or "")[:120],
                            "intake_id": meta.get("intake_id"),
                            "at": r.get("at_utc") or r.get("timestamp"),
                        }
                    )
            out["findings"]["upload_related_telemetry"] = intake_events[-40:]
            out["findings"]["upload_event_count"] = len(intake_events)
        else:
            out["findings"]["telemetry_status"] = tel.status_code

        for path in ("/api/operator/cockpit", "/api/cognitive-topology"):
            r = get(path)
            if r.status_code == 200:
                body = r.json()
                if path.endswith("cockpit"):
                    fb = body.get("founding_pilot") or body.get("intake") or {}
                    out["findings"]["cockpit_intake_metrics"] = fb.get("metrics") or fb
                else:
                    up = (body.get("subsystems") or {}).get("upload_pipeline") or {}
                    out["findings"]["cote_upload_pipeline"] = up

        out["findings"]["legacy_migration"] = inner.get("legacy_migration")
    finally:
        if client is not None:
            client.close()

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
