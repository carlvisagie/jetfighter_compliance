#!/usr/bin/env python3
"""Archive test intakes on production (or any KYC host). Uses scripts.lib.ops_client."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.lib.ops_client import OpsAuthError, authenticate_production  # noqa: E402

DEFAULT_IDS = [
    "FB-cfea103a466d",
    "FB-ba6760a59bc9",
    "FB-4ea7954a0ea6",
]


def main() -> int:
    ids = [x.strip() for x in (sys.argv[1:] or DEFAULT_IDS) if x.strip()]
    if not ids:
        print(json.dumps({"error": "No intake IDs provided"}, indent=2))
        return 1

    client = None
    try:
        client, headers, auth_diag = authenticate_production()
    except OpsAuthError as exc:
        print(json.dumps({"error": exc.reason, "auth_diagnostic": exc.diagnostic.as_dict()}, indent=2))
        return 1

    headers = {**headers, "Content-Type": "application/json"}
    try:
        results = []
        for iid in ids:
            r = client.post(
                "/api/operator/founding-pilot/action",
                headers=headers,
                json={"intake_id": iid, "action": "archive", "operator_note": "Launch cleanup — test intake archived"},
            )
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text[:300]}
            results.append(
                {
                    "intake_id": iid,
                    "status": r.status_code,
                    "ok": r.status_code == 200 and body.get("ok") is True,
                    "review_status": body.get("review_status"),
                    "detail": body.get("detail") if r.status_code != 200 else None,
                }
            )

        q = client.get("/api/operator/founding-pilot/queue", headers=headers)
        qbody = q.json() if q.status_code == 200 else {}
        active_ids = {row.get("intake_id") for row in qbody.get("queue") or []}
        still_visible = [iid for iid in ids if iid in active_ids]

        out = {
            "base_url": auth_diag.base_url,
            "auth_diagnostic": auth_diag.as_dict(),
            "archived": results,
            "still_in_active_queue": still_visible,
            "queue_depth": qbody.get("queue_depth"),
            "ok": all(r["ok"] for r in results) and not still_visible,
        }
        print(json.dumps(out, indent=2))
        return 0 if out["ok"] else 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
