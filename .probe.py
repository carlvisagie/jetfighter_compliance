"""Tiny one-shot probe used during deploy/recovery loops.

Run as:
    python .probe.py healthz
    python .probe.py build
    python .probe.py routes
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "https://jetfighter-compliance.onrender.com"


def _get(path: str, timeout: int = 15) -> dict:
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": "kyc-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            ctype = r.headers.get("content-type") or ""
            if "json" in ctype:
                return {"status": r.status, "json": json.loads(raw)}
            return {"status": r.status, "text": raw[:600]}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        return {"status": e.code, "error": str(e), "body": body}
    except Exception as e:
        return {"status": -1, "error": f"{type(e).__name__}: {e}"}


def _summarise_ei(payload: dict) -> dict:
    """Distill the EI operator payload down to the dimensions that
    matter for verifying the reprocess worked: profile, gaps, custody."""
    if not isinstance(payload, dict):
        return {"_raw": str(payload)[:200]}
    profile = payload.get("profile") or {}
    inventory = profile.get("document_inventory") or []
    gaps = payload.get("gaps") or []
    custody = payload.get("custody_chain") or payload.get("custody") or []
    return {
        "ok":             payload.get("ok"),
        "primary_domain": profile.get("primary_domain"),
        "domain_conf":    profile.get("domain_confidence"),
        "files_analyzed": len(inventory),
        "inventory":      [
            {"file": r.get("file"),
             "doc":  r.get("document_type"),
             "conf": r.get("confidence")}
            for r in inventory
        ][:25],
        "entity_buckets": {
            k: len(profile.get(k) or [])
            for k in ("company_name_candidates","emails","phones",
                      "addresses","domains","websites","people",
                      "vendors","compliance_references")
        },
        "gap_count":  len(gaps),
        "gap_ids":    [g.get("gap_id") for g in gaps[:15]],
        "custody_recent": [
            {"phase": c.get("phase"), "ok": c.get("ok"),
             "at":    c.get("at_utc"), "meta": c.get("metadata")}
            for c in list(custody)[-8:]
        ],
    }


def main(argv: list[str]) -> int:
    target = (argv[1] if len(argv) > 1 else "healthz").lower()
    if target == "binaries":
        out = _get("/healthz/ei-binaries")
        if isinstance(out.get("json"), dict):
            j = out["json"]
            tess = (j.get("tesseract_binary") or {})
            popp = (j.get("poppler_binary")   or {})
            out = {
                "status":         out["status"],
                "ok":             j.get("ok"),
                "ocr_enabled":    j.get("ocr_enabled"),
                "pytesseract":    j.get("pytesseract_import"),
                "pdf2image":      j.get("pdf2image_import"),
                "tesseract":      "available@" + str(tess.get("version") or "?") if tess.get("available") else f"missing: {tess.get('reason','?')}",
                "poppler":        "available@" + str(popp.get("version") or "?") if popp.get("available") else f"missing: {popp.get('reason','?')}",
            }
    elif target == "healthz":
        out = _get("/healthz")
    elif target == "build":
        out = _get("/api/public/build-info")
        if isinstance(out.get("json"), dict):
            out = {"status":     out["status"],
                   "git_commit": out["json"].get("git_commit"),
                   "build_time": out["json"].get("build_time"),
                   "environment":out["json"].get("environment")}
    elif target == "routes":
        # Use the new reprocess route as a deploy marker.
        # Pre-redeploy: 404 (route not registered).
        # Post-redeploy: 401/403 (auth gate hit -> code is live).
        # POST without body.
        url = BASE + "/api/operator/evidence-intelligence/reprocess/FB-000000000000"
        req = urllib.request.Request(url, method="POST",
                                     headers={"User-Agent": "kyc-probe/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                out = {"status": r.status, "marker": "ROUTE_LIVE"}
        except urllib.error.HTTPError as e:
            label = "ROUTE_LIVE" if e.code in (401, 403, 422) else "ROUTE_MISSING"
            out = {"status": e.code, "marker": label}
        except Exception as e:
            out = {"status": -1, "error": f"{type(e).__name__}: {e}"}
    elif target == "ei":
        # python .probe.py ei FB-xxxxxxxxxxxx
        iid = argv[2] if len(argv) > 2 else ""
        if not iid:
            print(json.dumps({"error": "intake_id required"}))
            return 1
        raw = _get(f"/api/operator/evidence-intelligence?project_id={iid}")
        if isinstance(raw.get("json"), dict):
            out = _summarise_ei(raw["json"])
        else:
            out = raw
    else:
        out = _get(target if target.startswith("/") else f"/{target}")
    print(json.dumps(out, indent=2, default=str)[:3500])
    return 0 if isinstance(out.get("status"), int) and 200 <= out["status"] < 500 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
