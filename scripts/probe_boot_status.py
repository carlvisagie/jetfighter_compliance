"""One-shot probe: authenticate and report scheduler boot entries from production."""

from __future__ import annotations

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

    print("Auth OK")
    print("  base_url      :", diag.base_url)
    print("  git_commit    :", diag.build_info.get("git_commit"))
    print("  service       :", diag.build_info.get("service"))
    print("  environment   :", diag.build_info.get("environment"))
    print()

    try:
        r = client.get("/api/ops/boot-status", headers=headers)
        body = r.json()
    except Exception as exc:
        print("boot-status request failed:", exc)
        return 2

    print("boot-status:")
    print("  safe_mode         :", body.get("safe_mode"))
    print("  schedulers_enabled:", body.get("schedulers_enabled"))
    print()
    print("scheduler/worker entries (most recent):")
    seen = 0
    entries = body.get("entries") or []
    for e in entries:
        c = e.get("component", "")
        if c in ("worker", "scheduler", "heavy_subsystems", "startup_warning"):
            print(f"  {c}: {e.get('status')} ({e.get('detail','')})")
            seen += 1
    if not seen:
        print("  (none — endpoint may not surface scheduler entries)")
    print()
    print(f"total entries returned: {len(entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
