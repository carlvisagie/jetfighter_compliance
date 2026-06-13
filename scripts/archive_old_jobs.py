"""Archive old test jobs to clean the queue."""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

jobs_dir = Path("data/jobs")
archive_dir = Path("data/jobs_archive")
archive_dir.mkdir(exist_ok=True)

print("=" * 80)
print("ARCHIVING OLD TEST JOBS")
print("=" * 80)

jobs = list(jobs_dir.glob("J-*.json"))
print(f"\nTotal jobs found: {len(jobs)}")

if not jobs:
    print("No jobs to archive.")
    exit(0)

# Analyze jobs
completed = []
pending = []
old_jobs = []

now = datetime.now(timezone.utc)

for job_file in jobs:
    try:
        data = json.loads(job_file.read_text(encoding="utf-8"))
        status = data.get("status", "unknown")
        created = data.get("created_utc", "")
        
        # Check if old (before June 5, 2026 - keeping only very recent jobs)
        if created and (created.startswith("2026-05") or created.startswith("2026-06-0") and created < "2026-06-05"):
            old_jobs.append((job_file, status, created))
        
        if status == "completed":
            completed.append(job_file)
        elif status in ("pending", "queued"):
            pending.append(job_file)
    except Exception as e:
        print(f"Error reading {job_file.name}: {e}")

print(f"\nCompleted jobs: {len(completed)}")
print(f"Pending jobs: {len(pending)}")
print(f"Old jobs (May 2026): {len(old_jobs)}")

# Archive old May jobs
if old_jobs:
    print(f"\nArchiving {len(old_jobs)} old test jobs...")
    archived_count = 0
    
    for job_file, status, created in old_jobs:
        try:
            dest = archive_dir / job_file.name
            shutil.move(str(job_file), str(dest))
            archived_count += 1
            if archived_count <= 10:
                print(f"  Archived: {job_file.name} (status: {status}, created: {created})")
        except Exception as e:
            print(f"  Error archiving {job_file.name}: {e}")
    
    if archived_count > 10:
        print(f"  ... and {archived_count - 10} more")
    
    print(f"\nTotal archived: {archived_count}")

# Final count
remaining = list(jobs_dir.glob("J-*.json"))
print(f"\nRemaining jobs in queue: {len(remaining)}")

print("\n" + "=" * 80)
print("ARCHIVE COMPLETE")
print("=" * 80)
