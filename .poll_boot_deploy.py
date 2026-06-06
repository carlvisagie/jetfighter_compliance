"""Poll Render until the defensive boot ships in production vio.html.

Checks two things on each tick:
  1. /api/public/build-info reports git_commit starting with TARGET.
  2. /ui/vio.html contains the defensive-boot marker.
"""
import sys
import time
import json
import urllib.request as u

TARGET = "c7bf825"  # commit we just pushed
BUILD_INFO_URL = "https://jetfighter-compliance.onrender.com/api/public/build-info"
VIO_HTML_URL   = "https://jetfighter-compliance.onrender.com/ui/vio.html"
BOOT_MARKER    = "window.VIO_BOOT"

DEADLINE = time.time() + 420  # 7 minutes

start = time.time()
while time.time() < DEADLINE:
    elapsed = int(time.time() - start)
    git_commit = "?"
    boot_present = False
    try:
        bi = json.loads(u.urlopen(BUILD_INFO_URL, timeout=15).read())
        git_commit = (bi.get("git_commit") or bi.get("commit") or "?")[:8]
    except Exception as e:
        git_commit = f"err:{type(e).__name__}"
    try:
        html = u.urlopen(VIO_HTML_URL, timeout=15).read().decode("utf-8", "replace")
        boot_present = BOOT_MARKER in html
    except Exception as e:
        boot_present = False

    print(
        f"  [t={elapsed:3d}s] commit={git_commit:8s}  "
        f"target_match={git_commit.startswith(TARGET)}  "
        f"boot_in_vio_html={boot_present}",
        flush=True,
    )
    if git_commit.startswith(TARGET) and boot_present:
        print("DEPLOY_DONE", flush=True)
        sys.exit(0)
    time.sleep(20)

print("DEPLOY_TIMEOUT", flush=True)
sys.exit(1)
