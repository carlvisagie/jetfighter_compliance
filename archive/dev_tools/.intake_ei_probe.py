"""Read the operator EI snapshot for FB-1dfab13c120b post-reprocess."""
import json
import urllib.request

OPS_KEY = "939f0db78c714666a4a5686e751d13972b04975be65244d0a91841a38dfeb072"
BASE = "https://jetfighter-compliance.onrender.com"

paths = [
    "/api/operator/evidence-intelligence?project_id=FB-1dfab13c120b",
]

for p in paths:
    req = urllib.request.Request(BASE + p, headers={"X-Ops-Key": OPS_KEY})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", errors="replace")
            try:
                obj = json.loads(body)
                print(f"=== {p} ===")
                print(json.dumps(obj, indent=2)[:4000])
                print()
            except json.JSONDecodeError:
                print(f"=== {p} (non-JSON) ===")
                print(body[:1500])
    except Exception as e:
        print(f"=== {p} ===")
        print(f"err: {type(e).__name__}: {e}")
