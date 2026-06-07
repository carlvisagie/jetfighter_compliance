#!/usr/bin/env python3
"""PATCH 10C — repair stale expected/received metadata on production intakes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TARGETS = [
    "FB-17b89cc615a5",
    "FB-93647af95b99",
    "FB-55a9e236f916",
    "FB-1dfab13c120b",
]


def main() -> int:
    from scripts.lib.ops_client import OpsAuthError, authenticate_production

    try:
        client, _, diag = authenticate_production()
    except OpsAuthError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "diagnostic": exc.diagnostic.as_dict()}, indent=2))
        return 1

    results = []
    for iid in TARGETS:
        before = client.get(f"/api/operator/intake/reconcile/{iid}").json()
        repair = client.post(f"/api/operator/integrity/repair/{iid}").json()
        after = client.get(f"/api/operator/intake/reconcile/{iid}").json()
        results.append(
            {
                "intake_id": iid,
                "before": before.get("count_breakdown"),
                "before_issues": before.get("issues"),
                "repair": {
                    "ok": repair.get("ok"),
                    "action": repair.get("action"),
                    "root_cause": repair.get("root_cause"),
                    "repair_applied": repair.get("repair_applied"),
                    "plain_english": repair.get("plain_english"),
                    "before_truth": repair.get("before"),
                    "after_truth": repair.get("after"),
                },
                "after": after.get("count_breakdown"),
                "after_issues": after.get("issues"),
                "reconcile_ok": after.get("ok"),
            }
        )

    fleet = client.get("/api/operator/intake/reconcile?limit=200").json()
    proof = client.get("/api/operator/integrity/proof").json()
    build = client.get("/api/public/build-info").json()

    report = {
        "ok": all(r["reconcile_ok"] for r in results),
        "git_commit": build.get("git_commit"),
        "base_url": diag.base_url,
        "intakes": results,
        "failing_intake_ids": fleet.get("failing_intake_ids"),
        "fleet_integrity_ok": fleet.get("fleet_integrity_ok"),
        "integrity_proof_ok": proof.get("ok"),
        "evidence_vs_files": next(
            (
                s
                for s in (proof.get("subsystems") or [])
                if s.get("name") == "evidence_vs_files"
            ),
            None,
        ),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
