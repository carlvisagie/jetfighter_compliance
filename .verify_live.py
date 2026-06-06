"""Download live VIO JS bundles and parse-check them with node."""
import subprocess
import urllib.request as u

BASE = "https://jetfighter-compliance.onrender.com"
FILES = [
    "/ui/assets/js/vio.js",
    "/ui/assets/js/vio-level2.js",
    "/ui/assets/js/env-ribbon.js",
    "/ui/assets/js/organism-intel.js",
]

for path in FILES:
    body = u.urlopen(BASE + path, timeout=15).read().decode("utf-8", "replace")
    name = path.split("/")[-1]
    local = f".live-{name}"
    with open(local, "w", encoding="utf-8") as f:
        f.write(body)
    r = subprocess.run(["node", "--check", local], capture_output=True, text=True)
    status = "PARSE_OK" if r.returncode == 0 else f"PARSE_FAIL: {r.stderr.strip()[:200]}"
    print(f"  {len(body):>6}b  {name:25}  {status}")
