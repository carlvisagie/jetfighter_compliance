"""Final consolidated sanity check on the production deploy."""
import json
import sys
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://jetfighter-compliance.onrender.com"
KEY  = "939f0db78c714666a4a5686e751d13972b04975be65244d0a91841a38dfeb072"


def get_text(path, auth=False):
    headers = {"X-Ops-Key": KEY} if auth else {}
    req = u.Request(BASE + path, headers=headers)
    return u.urlopen(req, timeout=20).read().decode("utf-8", "replace")


def get_json(path, auth=True):
    return json.loads(get_text(path, auth=auth))


print("═" * 70)
print(" FINAL CONSOLIDATED CHECK — production deploy")
print("═" * 70)

# 1. Inline boot still in vio.html
html = get_text("/ui/vio.html", auth=True)
boot_ok = (
    "window.VIO_BOOT"   in html and
    "still initialising" in html and
    "boot-timeout"       in html and
    "unhandledrejection" in html
)
print(f"\n[1] Defensive boot in /ui/vio.html ……………………  {'OK' if boot_ok else 'FAIL'}")

# 2. New renderer in vio.js
js = get_text("/ui/assets/js/vio.js")
shapes = ["_svgSquare", "_svgTriangle", "_svgHexagon",
          "_svgCircle", "_svgDiamond", "_svgStarburst"]
events = ["intake", "upload", "analysis", "gap",
          "confirmation", "payment", "error", "complete"]
shapes_ok = all(s in js for s in shapes)
events_ok = all(f"'{e}'" in js for e in events)
ready_guard_ok = "render-empty" in js
print(f"[2] Sketch primitives in vio.js …………………………  {'OK' if shapes_ok else 'FAIL'}")
print(f"[3] Event types mapped in vio.js …………………………  {'OK' if events_ok else 'FAIL'}")
print(f"[4] Visibility safeguard in vio.js ……………………  {'OK' if ready_guard_ok else 'FAIL'}")

# 3. CSS for the new orb + shapes
css = get_text("/ui/assets/styles/vio.css")
css_ok = (
    ".vio-id-orb"                       in css and
    '.vio-event[data-color="green"]'    in css and
    '.vio-event[data-color="amber"]'    in css and
    '.vio-event[data-color="red"]'      in css and
    '.vio-event[data-color="blue"]'     in css and
    '.vio-event[data-color="grey"]'     in css and
    ".vio-backbone { display: none; }"  in css and
    "@keyframes vio-breathe"            in css
)
print(f"[5] New CSS classes live ………………………………………  {'OK' if css_ok else 'FAIL'}")

# 4. API returns the company we expect, with a timeline
overview = get_json("/api/operator/vio/overview?limit=10")
comps = overview.get("companies") or []
target = next((c for c in comps if "purposefullive" in (c.get("company_name") or "").lower()), None)
if target:
    tl = target.get("timeline") or []
    print(f"[6] API: purposefullivecoaching.com present  ……  OK")
    print(f"    intake_id    : {target.get('intake_id')}")
    print(f"    stage        : {target.get('stage')!r}")
    print(f"    stage_state  : {target.get('stage_state')!r}")
    print(f"    on_branch    : {target.get('on_branch')}")
    print(f"    timeline ({len(tl)} events):")
    for ev in tl:
        print(f"      · {ev.get('type'):14s} status={ev.get('status'):10s} {ev.get('label')!r}")
else:
    print(f"[6] API: target company present ……………………  FAIL  (got {len(comps)} companies)")

# Summary
all_ok = boot_ok and shapes_ok and events_ok and ready_guard_ok and css_ok and bool(target)
print()
print("═" * 70)
print(f"  RESULT: {'ALL GREEN — Carl can wake to a visible spine.' if all_ok else 'PROBLEMS — see above.'}")
print("═" * 70)
sys.exit(0 if all_ok else 1)
