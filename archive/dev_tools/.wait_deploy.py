import urllib.request, json, time, sys

TARGET = "c3e68ab"
URL = "https://jetfighter-compliance.onrender.com/api/public/build-info"
print(f"waiting for deploy of {TARGET}...", flush=True)
start = time.time()
last = ""
while time.time() - start < 240:
    try:
        d = json.loads(urllib.request.urlopen(URL, timeout=10).read())
        commit = (d.get("git_commit") or "")[:7]
        if commit != last:
            print(f"[{int(time.time()-start)}s] commit={commit}", flush=True)
            last = commit
        if commit == TARGET:
            print("DEPLOYED")
            sys.exit(0)
    except Exception as e:
        print(f"[{int(time.time()-start)}s] err: {e}", flush=True)
    time.sleep(10)
print("TIMEOUT")
sys.exit(1)
