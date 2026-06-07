import urllib.request as u

URL = "https://jetfighter-compliance.onrender.com/ui/vio.html"
OPS_KEY = "939f0db78c714666a4a5686e751d13972b04975be65244d0a91841a38dfeb072"

req = u.Request(URL, headers={"X-Ops-Key": OPS_KEY})
try:
    resp = u.urlopen(req, timeout=20)
    html = resp.read().decode("utf-8", "replace")
    status = resp.status
except Exception as e:
    print("ERROR:", type(e).__name__, e)
    raise SystemExit(1)

print("STATUS:", status)
print("LEN:", len(html))
print("HAS VIO_BOOT:           ", "window.VIO_BOOT" in html)
print("HAS SOFT WATCHDOG (2s): ", "2000" in html and "still initialising" in html)
print("HAS HARD WATCHDOG (10s):", "10000" in html and "boot-timeout" in html)
print("HAS ERROR TRAP:         ", "addEventListener('error'" in html)
print("HAS PROMISE TRAP:       ", "unhandledrejection" in html)
print()
print("FIRST 500 CHARS:")
print(html[:500])
