"""KYC production data audit — queries every available operator endpoint.

PRODUCTION IS THE ONLY TRUTH. Auth follows the single sanctioned script
contract (`scripts/lib/ops_client.authenticate_production`) — reads
``OPS_PASSWORD`` from the environment or ``.ops_env`` and exchanges it for
a session cookie. No hardcoded credentials. No ``--local`` / ``--target``.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts._prod_only import reject_target_flag  # noqa: E402
from scripts.lib.ops_client import OpsAuthError, authenticate_production  # noqa: E402

reject_target_flag()


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def _pp(label: str, value) -> None:
    print(f"  {label}: {value}")


def _get(client, headers, path: str, params: dict | None = None):
    r = client.get(path, headers=headers, params=params or {})
    if r.status_code != 200:
        return r.status_code, {"_error": r.text[:300]}
    try:
        return r.status_code, r.json()
    except Exception as exc:
        return r.status_code, {"_error": f"non-json: {exc}"}


def main() -> int:
    try:
        client, headers, diag = authenticate_production()
    except OpsAuthError as exc:
        print(f"AUTH FAIL: {exc.reason}")
        return 1

    print(
        f"  [OK] Authenticated  base={diag.base_url}  "
        f"git={diag.build_info.get('git_commit')}  "
        f"({datetime.now(timezone.utc).isoformat()})"
    )

    # ── INTAKE ENGINE ─────────────────────────────────────────────
    _section("INTAKE ENGINE")
    _, diag_body = _get(client, headers, "/api/operator/intake/diagnostics")
    d = diag_body.get("diagnostics", {}) or {}
    for key in (
        "data_root",
        "intake_directories_found",
        "upload_files_on_disk",
        "index_exists",
        "pending_review_count",
        "durable_storage_configured",
    ):
        _pp(key, d.get(key))

    _, q = _get(
        client,
        headers,
        "/api/operator/intake/queue",
        {"limit": 20, "include_archived": "true"},
    )
    queue = q.get("queue") or []
    _pp("queue_depth (pending)", q.get("queue_depth"))
    _pp("queue_rows_generated", q.get("queue_rows_generated"))
    _pp("queue_empty_reason", q.get("queue_empty_reason"))
    _pp("Total intakes returned", len(queue))
    print("\n  Last 20 intakes (from queue):")
    if not queue:
        print("    (none)")
    for row in queue[:20]:
        pid = row.get("project_id") or ""
        fc = row.get("file_count", 0)
        rs = row.get("review_status", "?")
        co = (row.get("company") or "(unnamed)")[:35]
        iid = row.get("intake_id", "?")
        print(
            f"    {iid}  company={co:35}  files={fc}  status={rs}  "
            f"project={pid or '(none)'}"
        )

    # ── DISK SCAN ─────────────────────────────────────────────────
    _section("RAW DISK SCAN")
    code, scan = _get(client, headers, "/api/operator/intake/raw-disk-scan")
    if code == 200:
        inv = scan.get("inventory") or scan
        for key in (
            "intake_directories",
            "intake_json_files",
            "upload_files",
            "index_tail_unique_ids",
        ):
            _pp(key, inv.get(key))
        print(f"  intake_ids_sample: {inv.get('intake_ids_sample') or []}")
    else:
        print(f"  raw-disk-scan returned {code}")

    # ── MEMORY / PROJECTS ─────────────────────────────────────────
    _section("MEMORY / PROJECTS")
    code, mem = _get(client, headers, "/api/operator/memory")
    if code == 200:
        stats = mem.get("stats") or {}
        for key in ("entity_count", "timeline_count", "signal_count"):
            _pp(key, stats.get(key))
    else:
        print(f"  /api/operator/memory -> {code}")

    code, ct = _get(client, headers, "/api/cognitive-topology")
    if code == 200:
        nodes = ct.get("nodes") or []
        proj_nodes = [n for n in nodes if "project" in str(n.get("type", "")).lower()]
        _pp("cognitive_topology nodes", len(nodes))
        _pp("project-type nodes", len(proj_nodes))

    # ── VIO OVERVIEW ──────────────────────────────────────────────
    _section("VIO OVERVIEW")
    _, vio = _get(client, headers, "/api/operator/vio/overview")
    companies = vio.get("companies") or []
    _pp("companies_visible", len(companies))
    _pp("health_score", (vio.get("organism_health") or {}).get("score"))
    _pp("state_breakdown", (vio.get("organism_health") or {}).get("state_counts"))
    for c in companies[:20]:
        print(
            f"    state={(c.get('state') or '?'):18} "
            f"company={(c.get('company_name') or '?')[:40]}"
        )

    # ── ORGANISM STATUS ───────────────────────────────────────────
    _section("ORGANISM STATUS")
    code, status = _get(client, headers, "/api/operator/organism/state")
    if code == 200:
        _pp("health_state", status.get("health_state"))
        _pp("environment", status.get("environment"))
        _pp("git_commit", status.get("git_commit"))
        _pp("durable_storage_configured", status.get("durable_storage_configured"))
        _pp("disk_persistence_state", status.get("disk_persistence_state"))
        _pp("disk_persistence_verified", status.get("disk_persistence_verified"))
        _pp("current_bottleneck", status.get("current_bottleneck"))
        _pp("next_recommended_action", status.get("next_recommended_action"))

    # ── COCKPIT ───────────────────────────────────────────────────
    _section("OPERATOR COCKPIT SUMMARY")
    code, ck = _get(client, headers, "/api/operator/control-room")
    if code != 200:
        code, ck = _get(client, headers, "/api/operator/cockpit")
    if code == 200:
        _pp("cockpit_ok", ck.get("ok"))
        stats = ck.get("stats") or ck.get("summary") or {}
        for k, v in stats.items():
            _pp(k, v)
    else:
        print(f"  cockpit -> {code}")

    # ── ACQUISITION ───────────────────────────────────────────────
    _section("ACQUISITION ENGINE")
    code, acq = _get(client, headers, "/api/operator/acquisition/status")
    if code == 200:
        stats = acq.get("stats") or {}
        _pp("leads_total", stats.get("total_leads"))
        _pp("leads_pending", stats.get("pending_approval"))
        _pp("leads_approved", stats.get("approved"))

    # ── PAYMENT ───────────────────────────────────────────────────
    _section("PAYMENT ENGINE")
    code, pay = _get(client, headers, "/api/operator/payment-products")
    if code == 200:
        prods = pay.get("products") or []
        _pp("payment_products_configured", len(prods))
        for p in prods[:5]:
            _pp(
                "  product",
                f"{p.get('name','?')} | {p.get('price_formatted','?')} | "
                f"id={p.get('product_id','?')}",
            )

    # ── HEALTHZ ───────────────────────────────────────────────────
    _section("HEALTHZ")
    code, hz = _get(client, headers, "/healthz")
    _pp("health", hz.get("status") or hz.get("ok"))
    subsystems = hz.get("subsystems") or hz.get("checks") or {}
    for k, v in subsystems.items():
        _pp(f"  {k}", v)

    print(f"\n{'=' * 60}\n  AUDIT COMPLETE\n{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
