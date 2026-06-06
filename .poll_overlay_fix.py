"""Poll until the L2-mount fix is on production CSS."""
import sys, time, urllib.request as u
URL = "https://jetfighter-compliance.onrender.com/ui/assets/styles/vio.css"
MARKER = ".vio-level2-mount[hidden]"
DEADLINE = time.time() + 540
start = time.time()
while time.time() < DEADLINE:
    elapsed = int(time.time() - start)
    try:
        css = u.urlopen(URL, timeout=15).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  [t={elapsed:3d}s] fetch err: {type(e).__name__}", flush=True)
        time.sleep(20); continue
    live = MARKER in css
    print(f"  [t={elapsed:3d}s] size={len(css):6d}  overlay_fix_live={live}", flush=True)
    if live:
        print("DEPLOY_DONE", flush=True); sys.exit(0)
    time.sleep(20)
print("DEPLOY_TIMEOUT", flush=True); sys.exit(1)
