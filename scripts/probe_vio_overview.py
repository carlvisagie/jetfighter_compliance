"""One-shot probe: read /api/operator/vio/overview and confirm organism shape."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.lib.ops_client import OpsAuthError, authenticate_production


def main() -> int:
    try:
        client, headers, diag = authenticate_production()
    except OpsAuthError as exc:
        print("AUTH FAIL:", exc.reason)
        return 1

    r = client.get("/api/operator/vio/overview?limit=120", headers=headers)
    body = r.json()
    print("status                :", r.status_code)
    print("ok                    :", body.get("ok"))
    print("companies returned    :", len(body.get("companies") or []))
    print("queue_depth           :", body.get("queue_depth"))
    print("urgent_count          :", body.get("urgent_count"))
    print()
    org = body.get("organism") or {}
    print("organism keys         :", sorted(org.keys()))
    print()
    print("organism summary:")
    for k in (
        "available",
        "health_state",
        "current_bottleneck",
        "next_recommended_action",
        "queue_depth",
        "intake_count_active",
        "intake_count_total",
        "uploaded_file_count",
        "mismatch_count",
        "environment",
        "git_commit",
        "durable_storage_configured",
        "timestamp_utc",
    ):
        print(f"  {k:30s} = {org.get(k)!r}")

    if org.get("mismatches"):
        print()
        print("mismatches:")
        for m in org.get("mismatches"):
            print(f"  [{m.get('severity')}] {m.get('name')}: {m.get('detail')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
