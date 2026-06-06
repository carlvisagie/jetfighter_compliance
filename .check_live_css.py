import urllib.request as u
css = u.urlopen(
    "https://jetfighter-compliance.onrender.com/ui/assets/styles/vio.css",
    timeout=15,
).read().decode("utf-8", "replace")
print("SIZE:", len(css))
marker = ".vio-level2-mount[hidden]"
print("HAS MARKER:", marker in css)
i = css.find(marker)
if i >= 0:
    print("SNIPPET:", repr(css[i:i + 200]))
