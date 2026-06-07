"""Probe several live endpoints to triangulate which commit is on the box."""
import json
import time
import urllib.request

BASE = "https://jetfighter-compliance.onrender.com"


def fetch(path, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8", errors="replace")[:1500]
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else "")[:1500]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


paths = [
    "/healthz",
    "/api/public/build-info",
    "/healthz/ei-binaries",
    "/healthz/build-diagnostic",
    # Auth-required; we just want to know whether it 404s (not deployed) or 401/403 (deployed):
    "/api/ops/ei-freshness?dry_run=true",
]

for p in paths:
    s, b = fetch(p)
    print(f"[{s}] {p}\n    {b[:300]}\n")
