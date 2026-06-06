"""Probe the autonomous EI freshness sweep on production.

Hits /api/ops/ei-freshness?dry_run=true with the operator API key so
we can see WHAT the organism currently considers stale (without
triggering reprocesses). Then optionally re-runs with dry_run=false.
"""
import json
import os
import sys
import urllib.error
import urllib.request

OPS_KEY = "939f0db78c714666a4a5686e751d13972b04975be65244d0a91841a38dfeb072"

BASE = "https://jetfighter-compliance.onrender.com"


def probe(dry_run: bool):
    url = f"{BASE}/api/ops/ei-freshness?dry_run={'true' if dry_run else 'false'}"
    req = urllib.request.Request(url, headers={"X-Ops-Key": OPS_KEY})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            print(f"[{r.status}] {url}")
            print(json.dumps(data, indent=2)[:3000])
    except urllib.error.HTTPError as e:
        print(f"[{e.code}] {url}")
        try:
            print(e.read().decode("utf-8", errors="replace")[:1500])
        except Exception:
            pass
    except Exception as e:
        print(f"err: {type(e).__name__}: {e}")


print("=== dry run ===")
probe(dry_run=True)

if "--commit" in sys.argv:
    print("\n=== COMMIT (will trigger reprocess) ===")
    probe(dry_run=False)
