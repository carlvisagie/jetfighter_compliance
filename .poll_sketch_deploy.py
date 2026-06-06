"""Poll Render until the sketch renderer is live."""
import sys
import time
import urllib.request as u

URL_JS  = "https://jetfighter-compliance.onrender.com/ui/assets/js/vio.js"
URL_CSS = "https://jetfighter-compliance.onrender.com/ui/assets/styles/vio.css"

# Distinctive markers from THIS commit.
JS_MARKER  = "_svgStarburst"
CSS_MARKER = ".vio-id-orb"

DEADLINE = time.time() + 540  # 9 minutes
start = time.time()
while time.time() < DEADLINE:
    elapsed = int(time.time() - start)
    try:
        js  = u.urlopen(URL_JS,  timeout=15).read().decode("utf-8", "replace")
    except Exception as e:
        js = ""
        print(f"  [t={elapsed:3d}s]  js fetch err: {type(e).__name__}", flush=True)
    try:
        css = u.urlopen(URL_CSS, timeout=15).read().decode("utf-8", "replace")
    except Exception as e:
        css = ""
        print(f"  [t={elapsed:3d}s] css fetch err: {type(e).__name__}", flush=True)

    js_live  = JS_MARKER  in js
    css_live = CSS_MARKER in css
    print(
        f"  [t={elapsed:3d}s]  js_size={len(js):6d}  css_size={len(css):6d}  "
        f"js_live={js_live}  css_live={css_live}",
        flush=True,
    )
    if js_live and css_live:
        print("DEPLOY_DONE", flush=True)
        sys.exit(0)
    time.sleep(20)

print("DEPLOY_TIMEOUT", flush=True)
sys.exit(1)
