import urllib.request, json
URL = "https://jetfighter-compliance.onrender.com/api/public/build-info"
raw = urllib.request.urlopen(URL, timeout=10).read().decode()
print(raw)
try:
    d = json.loads(raw)
    print("---")
    print("commit:", d.get("git_commit"))
    print("built_at:", d.get("built_at"))
except Exception as e:
    print("parse error:", e)
