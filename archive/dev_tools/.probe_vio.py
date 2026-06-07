"""One-shot probe of the live VIO overview endpoint."""
import json
import sys
import urllib.request as u

URL = "https://jetfighter-compliance.onrender.com/api/operator/vio/overview?limit=60"

req = u.Request(URL)
try:
    r = u.urlopen(req, timeout=15)
    body = r.read().decode("utf-8", "replace")
    print("STATUS:", r.status)
    try:
        j = json.loads(body)
    except Exception as e:
        print("not json:", e)
        print("body[:300]=", body[:300])
        sys.exit(0)
    if isinstance(j, dict):
        keys = list(j.keys())
        print("top-level keys:", keys)
        for cand in ("companies", "rows", "items", "data", "intakes"):
            v = j.get(cand)
            if isinstance(v, list):
                print(f"  {cand}: {len(v)} entries")
                if v:
                    print(f"    first entry keys: {list(v[0].keys())[:15]}")
        env = j.get("_env")
        print("  _env:", env)
        err = j.get("error") or j.get("detail")
        if err:
            print("  ERROR:", err)
    else:
        size = len(j) if hasattr(j, "__len__") else "n/a"
        print("top-level type:", type(j).__name__, "size:", size)
except u.HTTPError as he:
    print("HTTPError", he.code)
    print("body:", he.read()[:400])
except Exception as e:
    print("FAILED", type(e).__name__, e)
