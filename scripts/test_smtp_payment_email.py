#!/usr/bin/env python3
"""Safe production SMTP + payment-email verification (no secrets in output)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

import os  # noqa: E402

_ops_env = _REPO / ".ops_env"
if _ops_env.is_file():
    for line in _ops_env.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and not os.environ.get(k, "").strip():
            os.environ[k] = v

import httpx  # noqa: E402

from scripts.lib.ops_client import OpsAuthError, authenticate_production  # noqa: E402

BASE = "https://compliance.keepyourcontracts.com"
TEST_TO = "first-sale-live-test@keepyourcontracts.com"
TEST_INTAKE = "FB-661b0a5a12d6"
PRODUCT_ID = "cmmc_l1"


def _render_smtp_presence() -> Dict[str, Any]:
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        return {"ok": False, "reason": "RENDER_API_KEY not set"}
    sid = "srv-d83gut57vvec739efv6g"
    hc = httpx.Client(
        base_url="https://api.render.com",
        headers={"Authorization": f"Bearer {key}"},
        timeout=60,
    )
    try:
        r = hc.get(f"/v1/services/{sid}/env-vars")
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code}
        raw: Dict[str, str] = {}
        for item in r.json():
            ev = item.get("envVar") or item
            raw[str(ev.get("key") or "")] = str(ev.get("value") or "")

        host = raw.get("SMTP_HOST") or raw.get("SMTP_SERVER") or ""
        user = raw.get("SMTP_USER") or raw.get("SMTP_USERNAME") or ""
        pwd = raw.get("SMTP_PASS") or raw.get("SMTP_PASSWORD") or ""
        port = raw.get("SMTP_PORT") or "587"
        from_email = raw.get("SMTP_FROM_EMAIL") or raw.get("SMTP_FROM") or ""

        provider = "Gmail"
        if "sendgrid" in host.lower():
            provider = "SendGrid"
        elif "gmail" not in host.lower() and not user.endswith("@gmail.com"):
            provider = host or "unknown"

        return {
            "ok": True,
            "provider": provider,
            "SMTP_ENABLED": raw.get("SMTP_ENABLED"),
            "SMTP_HOST": raw.get("SMTP_HOST") or "(missing)",
            "SMTP_SERVER": raw.get("SMTP_SERVER") or "(missing)",
            "effective_host": host,
            "SMTP_PORT": port,
            "SMTP_USER": raw.get("SMTP_USER") or "(missing)",
            "SMTP_USERNAME": raw.get("SMTP_USERNAME") or "(missing)",
            "effective_user": user,
            "SMTP_PASS_set": bool(raw.get("SMTP_PASS")),
            "SMTP_PASSWORD_set": bool(raw.get("SMTP_PASSWORD")),
            "password_length": len(pwd) if pwd else 0,
            "SMTP_FROM_EMAIL": from_email or "(missing)",
            "SMTP_FROM_NAME": raw.get("SMTP_FROM_NAME") or "(missing)",
            "tls_mode": "STARTTLS on port 587 (smtplib SMTP + starttls)",
        }
    finally:
        hc.close()


def main() -> int:
    out: Dict[str, Any] = {
        "base": BASE,
        "test_to": TEST_TO,
        "test_intake": TEST_INTAKE,
    }

    out["render_env"] = _render_smtp_presence()

    client = httpx.Client(base_url=BASE, timeout=120, follow_redirects=True)
    try:
        client, _headers, _diag = authenticate_production(base_url=BASE, verify_deploy=False)
        smtp_status = client.get("/api/operator/smtp-status").json()
        out["live_smtp_status"] = smtp_status.get("smtp")

        test = client.post("/api/operator/test-email", json={"to": TEST_TO}).json()
        out["smtp_test"] = test.get("result") or test

        sent = bool((out["smtp_test"] or {}).get("sent"))
        if sent:
            pay = client.post(
                "/api/operator/founding-beta/action",
                json={
                    "intake_id": TEST_INTAKE,
                    "action": "send_payment_link",
                    "product_id": PRODUCT_ID,
                },
            ).json()
            email_result = (pay.get("email_result") or {}) if isinstance(pay, dict) else {}
            out["payment_link_retest"] = {
                "ok": pay.get("ok"),
                "intake_id": pay.get("intake_id"),
                "email_sent": bool(email_result.get("sent")),
                "email_error": email_result.get("error"),
                "email_detail": email_result.get("detail"),
            }
        else:
            out["payment_link_retest"] = {"skipped": True, "reason": "smtp_test_failed"}

        out["verdict"] = "PASS" if sent else "FAIL"
        print(json.dumps(out, indent=2))
        return 0 if sent else 1
    except OpsAuthError as exc:
        out["verdict"] = "FAIL"
        out["error"] = str(exc)
        print(json.dumps(out, indent=2))
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
