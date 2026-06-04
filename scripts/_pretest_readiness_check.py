"""Pre-test readiness verification — one-shot operator probe of the live
production environment. Read-only, side-effect-free except for the
optional --send-test-email flag which dispatches one Resend message.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("ERROR: pip install httpx")

BASE = "https://compliance.keepyourcontracts.com"
ENV_FILE = Path(__file__).resolve().parent.parent / ".ops_env"


def _load(name: str) -> str:
    v = os.getenv(name, "")
    if v:
        return v
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send-test-email", action="store_true",
                    help="Dispatch one operator test email via Resend")
    ap.add_argument("--test-email-to", default="",
                    help="Recipient for the test email")
    args = ap.parse_args()

    ops_password = _load("OPS_PASSWORD")
    if not ops_password:
        sys.exit("ERROR: OPS_PASSWORD missing in env and .ops_env")

    out: dict = {}
    with httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=False) as c:
        # 1. login
        r = c.post("/api/ops/login", json={"password": ops_password})
        r.raise_for_status()
        out["login"] = r.json()

        # 2. storage-status (the canonical durable storage probe)
        r = c.get("/api/operator/storage-status")
        out["storage_status_http"] = r.status_code
        out["storage_status"] = r.json() if r.status_code == 200 else r.text

        # 3. intake diagnostics
        r = c.get("/api/operator/intake/diagnostics")
        out["intake_diagnostics_http"] = r.status_code
        out["intake_diagnostics"] = r.json() if r.status_code == 200 else r.text

        # 4. organism state
        r = c.get("/api/operator/organism/state")
        out["organism_state_http"] = r.status_code
        out["organism_state"] = r.json() if r.status_code == 200 else r.text

        # 5. VIO overview (proves overview API + organism strip data)
        r = c.get("/api/operator/vio/overview")
        out["vio_overview_http"] = r.status_code
        if r.status_code == 200:
            body = r.json()
            out["vio_overview"] = {
                "total_companies": len(body.get("companies") or []),
                "has_organism_block": bool(body.get("organism")),
                "organism_keys": list((body.get("organism") or {}).keys()),
            }
        else:
            out["vio_overview"] = r.text

        # 6. VIO HTML page reachable
        r = c.get("/ui/vio.html")
        out["vio_html_http"] = r.status_code
        out["vio_html_bytes"] = len(r.text) if r.status_code == 200 else 0

        # 7. ops version (build info, includes data_root)
        r = c.get("/api/ops/version")
        out["ops_version_http"] = r.status_code
        out["ops_version"] = r.json() if r.status_code == 200 else r.text

        # 8. optional test email
        if args.send_test_email:
            payload = {}
            if args.test_email_to:
                payload["to"] = args.test_email_to
            r = c.post("/api/operator/test-email", json=payload)
            out["test_email_http"] = r.status_code
            out["test_email"] = r.json() if r.status_code == 200 else r.text

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
