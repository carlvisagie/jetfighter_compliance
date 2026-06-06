"""Diagnose: VIO is dark after deploy. Find root cause without guessing."""
import json
import urllib.request as u

BASE    = "https://jetfighter-compliance.onrender.com"
OPS_KEY = "939f0db78c714666a4a5686e751d13972b04975be65244d0a91841a38dfeb072"


def get(path, json_resp=False):
    req = u.Request(BASE + path, headers={"X-Ops-Key": OPS_KEY})
    resp = u.urlopen(req, timeout=20)
    body = resp.read().decode("utf-8", "replace")
    if json_resp:
        try:
            return resp.status, json.loads(body)
        except Exception as e:
            return resp.status, {"_parse_error": str(e), "_raw": body[:300]}
    return resp.status, body


# ── 1. Does the live HTML have the boot? ────────────────────────────────────
print("=" * 70)
print("1. /ui/vio.html — is the defensive boot actually there?")
print("=" * 70)
status, html = get("/ui/vio.html")
print(f"status: {status}")
print(f"length: {len(html)}")
print(f"has window.VIO_BOOT: {'window.VIO_BOOT' in html}")
print(f"has boot IIFE:       {chr(40) + 'function () {' in html}")
print(f"has overlay paint:   {'vio-boot' in html}")
# Find the boot script tag position relative to other scripts
boot_pos    = html.find("window.VIO_BOOT")
ribbon_pos  = html.find('env-ribbon.js')
l2_pos      = html.find('vio-level2.js')
vio_js_pos  = html.find('"/ui/assets/js/vio.js"')
print(f"\nscript order (smaller = earlier in HTML):")
print(f"  inline boot     : {boot_pos}")
print(f"  env-ribbon.js   : {ribbon_pos}")
print(f"  vio-level2.js   : {l2_pos}")
print(f"  vio.js          : {vio_js_pos}")

# ── 2. What does the API actually return? ───────────────────────────────────
print()
print("=" * 70)
print("2. /api/operator/vio/overview — what data is VIO being given?")
print("=" * 70)
try:
    status, data = get("/api/operator/vio/overview", json_resp=True)
    print(f"status: {status}")
    if isinstance(data, dict):
        comps = data.get("companies", [])
        org   = data.get("organism", {})
        env   = data.get("_env", {})
        print(f"companies count: {len(comps)}")
        print(f"organism keys  : {list(org.keys()) if isinstance(org, dict) else 'NOT DICT'}")
        print(f"_env           : {env}")
        if comps:
            print(f"\nfirst 3 companies:")
            for c in comps[:3]:
                print(f"  - intake_id: {c.get('intake_id')}  "
                      f"company: {c.get('company_name') or c.get('name')!r}  "
                      f"phase: {c.get('phase')}")
        else:
            print("\n*** 0 COMPANIES RETURNED — VIO HAS NOTHING TO RENDER ***")
            print(f"full payload sample: {json.dumps(data, default=str)[:500]}")
    else:
        print(f"unexpected payload: {data!r}")
except Exception as e:
    print(f"API ERROR: {type(e).__name__}: {e}")

# ── 3. Is there any intake data on disk that we'd EXPECT to see? ────────────
print()
print("=" * 70)
print("3. /api/operator/intakes — what intakes does the backend know about?")
print("=" * 70)
try:
    status, data = get("/api/operator/intakes", json_resp=True)
    print(f"status: {status}")
    if isinstance(data, dict):
        items = data.get("intakes") or data.get("items") or []
        print(f"intake count: {len(items)}")
        if items:
            print("first 5:")
            for it in items[:5]:
                print(f"  - {it.get('intake_id')}  "
                      f"{(it.get('company_name') or it.get('display_name') or '?')!r}  "
                      f"phase={it.get('phase')}  "
                      f"created={it.get('created_at')}")
    else:
        print(f"payload: {str(data)[:300]}")
except Exception as e:
    print(f"API ERROR: {type(e).__name__}: {e}")

print()
print("=" * 70)
print("4. /ui/assets/js/vio.js — does the live JS call VIO_BOOT.ready()?")
print("=" * 70)
status, js = get("/ui/assets/js/vio.js")
print(f"status: {status}")
print(f"length: {len(js)}")
print(f"calls VIO_BOOT.ready: {'VIO_BOOT.ready' in js}")
print(f"calls VIO_BOOT.fault: {'VIO_BOOT.fault' in js}")

print()
print("DONE")
