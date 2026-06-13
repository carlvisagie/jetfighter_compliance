from pathlib import Path

jobs = Path("data/jobs")
if jobs.exists():
    pending = list(jobs.glob("J-*.json"))
    print(f"Jobs directory exists: True")
    print(f"Pending jobs: {len(pending)}")
    if pending:
        print("\nPending job files:")
        for j in pending[:10]:
            print(f"  {j.name}")
else:
    print("Jobs directory exists: False")
