"""Check target structure."""
from pathlib import Path
import json

TARGETS = Path("E:/JetFighter_Compliance/data/acquisition/targets.jsonl")

if TARGETS.is_file():
    lines = TARGETS.read_text(encoding="utf-8").strip().split("\n")
    print(f"Found {len(lines)} targets")
    
    if lines:
        first = json.loads(lines[0])
        print("\nFirst target fields:")
        for key in sorted(first.keys()):
            print(f"  {key}: {type(first[key]).__name__}")
        
        print("\n\nFirst target sample:")
        print(json.dumps(first, indent=2)[:1000])
else:
    print("No targets.jsonl found")
