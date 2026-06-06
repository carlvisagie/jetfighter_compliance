"""Poll Render until the parse-fix lands in production vio-level2.js."""
import sys
import time
import urllib.request as u

URL = "https://jetfighter-compliance.onrender.com/ui/assets/js/vio-level2.js"
MARKER = "idx already computed above"
DEADLINE = time.time() + 360  # 6 minutes

while time.time() < DEADLINE:
    try:
        body = u.urlopen(URL, timeout=15).read().decode("utf-8", "replace")
        has_marker = MARKER in body
        elapsed = int(time.time() % 1000)
        print(f"  [t={elapsed:4d}s] live JS size={len(body)}  fix_landed={has_marker}", flush=True)
        if has_marker:
            print("DEPLOY_DONE", flush=True)
            sys.exit(0)
    except Exception as e:
        print(f"  [poll error] {type(e).__name__}: {e}", flush=True)
    time.sleep(30)

print("DEPLOY_TIMEOUT", flush=True)
sys.exit(1)
