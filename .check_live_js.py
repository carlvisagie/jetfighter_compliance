import urllib.request

URLS = [
    "https://jetfighter-compliance.onrender.com/ui/assets/js/vio-level2.js",
    "https://jetfighter-compliance.onrender.com/ui/assets/js/vio.js",
]
SIGNATURES = {
    "vio-level2.js": [
        "if (!axis) axis = _timeAxis(detail);",      # the L2 skeleton fix
        "VIO_BOOT.fault('l2-load-failed'",            # the L2 fault hook
    ],
    "vio.js": [
        "VIO_BOOT.ready()",
        "VIO_BOOT.fault",
    ],
}

for url in URLS:
    print(f"--- {url}")
    text = urllib.request.urlopen(url, timeout=15).read().decode()
    name = url.rsplit("/", 1)[-1]
    for sig in SIGNATURES.get(name, []):
        present = sig in text
        print(f"  {'OK' if present else 'MISSING'} :: {sig}")
    print(f"  bytes={len(text)}")
