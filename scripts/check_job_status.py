from pathlib import Path
import json

jobs = Path("data/jobs")
if not jobs.exists():
    print("No jobs directory")
    exit()

pending = list(jobs.glob("J-*.json"))
print(f"Total jobs: {len(pending)}\n")

status_counts = {}
for j in pending[:50]:  # Sample first 50
    try:
        data = json.loads(j.read_text())
        status = data.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    except:
        status_counts["error_reading"] = status_counts.get("error_reading", 0) + 1

print("Status breakdown (sample of 50):")
for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")

# Check a completed job
for j in pending[:10]:
    try:
        data = json.loads(j.read_text())
        if data.get("status") == "done":
            print(f"\nSample completed job: {j.name}")
            print(f"  Created: {data.get('created_utc')}")
            print(f"  Status: {data.get('status')}")
            print(f"  Attempts: {data.get('attempts')}")
            print(f"  Result: {bool(data.get('result'))}")
            break
    except:
        pass
