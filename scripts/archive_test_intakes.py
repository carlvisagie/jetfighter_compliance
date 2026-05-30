#!/usr/bin/env python3
"""Archive test intakes on production (or any KYC host). Requires OPS_PASSWORD or OPS_API_KEY."""
from __future__ import annotations

import json
import os
import sys

import httpx

BASE = os.environ.get("PROD_BASE_URL", "https://compliance.keepyourcontracts.com")
OPS_PASSWORD = os.environ.get("OPS_PASSWORD", "")
OPS_API_KEY = os.environ.get("OPS_API_KEY", "")

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

    headers: dict[str, str] = {"Content-Type": "application/json"}
    with httpx.Client(base_url=BASE, timeout=60.0, follow_redirects=False) as client:
        if OPS_API_KEY:
            headers["X-Ops-Key"] = OPS_API_KEY
        elif OPS_PASSWORD:
            login = client.post("/api/ops/login", json={"password": OPS_PASSWORD})
            if login.status_code != 200 or not login.json().get("ok"):
                print(json.dumps({"error": "ops login failed", "status": login.status_code}, indent=2))
                return 1
        else:
            print(json.dumps({"error": "Set OPS_PASSWORD or OPS_API_KEY"}, indent=2))
            return 1

        results = []
        for iid in ids:
            r = client.post(
                "/api/operator/founding-beta/action",
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

        q = client.get("/api/operator/founding-beta/queue", headers=headers)
        qbody = q.json() if q.status_code == 200 else {}
        active_ids = {row.get("intake_id") for row in qbody.get("queue") or []}
        still_visible = [iid for iid in ids if iid in active_ids]

        out = {
            "base_url": BASE,
            "archived": results,
            "still_in_active_queue": still_visible,
            "queue_depth": qbody.get("queue_depth"),
            "ok": all(r["ok"] for r in results) and not still_visible,
        }
        print(json.dumps(out, indent=2))
        return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
