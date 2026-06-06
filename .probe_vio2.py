"""Probe live VIO assets and surface 4xx/5xx silently failing."""
import urllib.request as u

ASSETS = [
    "/ui/vio.html",
    "/ui/assets/styles/vio.css",
    "/ui/assets/styles/env-ribbon.css",
    "/ui/assets/js/vio.js",
    "/ui/assets/js/vio-level2.js",
    "/ui/assets/js/env-ribbon.js",
]
BASE = "https://jetfighter-compliance.onrender.com"

for path in ASSETS:
    try:
        r = u.urlopen(BASE + path, timeout=15)
        body = r.read()
        print(f"  [{r.status}] {len(body):>7}b  {path}")
    except u.HTTPError as he:
        print(f"  [{he.code}] FAIL     {path}  body[:120]={he.read()[:120]!r}")
    except Exception as e:
        print(f"  [ERR] FAIL     {path}  {type(e).__name__}: {e}")
