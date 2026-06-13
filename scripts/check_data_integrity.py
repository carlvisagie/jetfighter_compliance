"""Check for data integrity and storage issues."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path("E:/JetFighter_Compliance")
DATA_DIR = ROOT / "data"

print("=" * 80)
print("DATA INTEGRITY CHECK")
print("=" * 80)

issues = []

# 1. Check for corrupted JSON files
print("\n[1] Checking for corrupted JSON files...")
json_files = list(DATA_DIR.rglob("*.json"))
corrupted = []

for f in json_files[:100]:  # Sample first 100
    try:
        if f.stat().st_size > 0:
            json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        corrupted.append((str(f.relative_to(ROOT)), str(e)[:60]))
    except Exception:
        pass

if corrupted:
    print(f"[WARN] Found {len(corrupted)} corrupted JSON files:")
    for path, error in corrupted[:10]:
        print(f"  {path}: {error}")
else:
    print(f"[OK] No corrupted JSON files (checked {len(json_files[:100])} files)")

# 2. Check for empty critical files
print("\n[2] Checking for empty critical files...")
critical_files = [
    "data/memory/telemetry.jsonl",
    "data/memory/timeline.jsonl",
    "data/memory/learning_state.json",
]

empty_critical = []
for path in critical_files:
    f = ROOT / path
    if f.is_file():
        size = f.stat().st_size
        if size == 0:
            empty_critical.append(path)
        elif size < 100:
            print(f"[WARN] {path}: only {size} bytes")
    else:
        print(f"[MISSING] {path}: file does not exist")

if empty_critical:
    print(f"[WARN] Empty critical files: {empty_critical}")
else:
    print("[OK] All critical files have content")

# 3. Check data directory permissions
print("\n[3] Checking data directory structure...")
required_dirs = [
    "data/memory",
    "data/intakes",
    "data/projects",
    "data/jobs",
    "data/acquisition",
    "data/alerts",
]

missing_dirs = []
for path in required_dirs:
    d = ROOT / path
    if not d.is_dir():
        missing_dirs.append(path)

if missing_dirs:
    print(f"[WARN] Missing directories: {missing_dirs}")
else:
    print("[OK] All required directories exist")

# 4. Check for orphaned files (files without parent records)
print("\n[4] Checking for orphaned intake files...")
intakes_dir = DATA_DIR / "intakes"
if intakes_dir.is_dir():
    intake_folders = [d for d in intakes_dir.iterdir() if d.is_dir()]
    orphaned = []
    
    for folder in intake_folders[:50]:  # Sample first 50
        intake_json = folder / "intake.json"
        if not intake_json.is_file():
            orphaned.append(str(folder.name))
    
    if orphaned:
        print(f"[WARN] Found {len(orphaned)} orphaned intake folders (no intake.json):")
        for name in orphaned[:10]:
            print(f"  {name}")
    else:
        print(f"[OK] No orphaned intakes (checked {len(intake_folders[:50])} folders)")
else:
    print("[WARN] Intakes directory not found")

# 5. Check for stale jobs
print("\n[5] Checking for stale jobs...")
jobs_dir = DATA_DIR / "jobs"
if jobs_dir.is_dir():
    job_files = list(jobs_dir.glob("*.json"))
    print(f"[INFO] Found {len(job_files)} job files")
    
    if len(job_files) > 100:
        print(f"[WARN] High job count: {len(job_files)} jobs (should be < 100)")
else:
    print("[INFO] No jobs directory or no jobs")

# 6. Check telemetry file size
print("\n[6] Checking telemetry file size...")
telem = DATA_DIR / "memory" / "telemetry.jsonl"
if telem.is_file():
    size_mb = telem.stat().st_size / (1024 * 1024)
    print(f"[INFO] Telemetry size: {size_mb:.2f} MB")
    if size_mb > 50:
        print(f"[WARN] Telemetry file is large (> 50 MB), may cause performance issues")
else:
    print("[WARN] Telemetry file not found")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_issues = len(corrupted) + len(empty_critical) + len(missing_dirs) + len(orphaned)

print(f"\nTotal data issues: {total_issues}")
print(f"  Corrupted JSON files: {len(corrupted)}")
print(f"  Empty critical files: {len(empty_critical)}")
print(f"  Missing directories: {len(missing_dirs)}")
print(f"  Orphaned intakes: {len(orphaned)}")

if total_issues > 0:
    print("\n[ACTION] Review and fix data integrity issues")
else:
    print("\n[SUCCESS] No critical data integrity issues found")

print("\n" + "=" * 80)
