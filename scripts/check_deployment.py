"""Simple deployment check without auth."""
import httpx
import time

print("Waiting 90 seconds for deployment...")
time.sleep(90)

client = httpx.Client()
r = client.get('https://compliance.keepyourcontracts.com/api/public/build-info')

if r.status_code == 200:
    build = r.json()
    current = build.get('git_commit', 'unknown')[:7]
    target = 'b5a1f25'
    print(f"Current commit: {current}")
    print(f"Target commit: {target}")
    print(f"Match: {current == target}")
    
    if current == target:
        print("\nDEPLOYMENT COMPLETE! Fix is live.")
    else:
        print("\nStill deploying...")
else:
    print(f"ERROR: Build info returned {r.status_code}")
