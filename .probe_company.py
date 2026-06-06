"""Probe one company's full payload from the live API."""
import json
import sys
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://jetfighter-compliance.onrender.com"
KEY  = "939f0db78c714666a4a5686e751d13972b04975be65244d0a91841a38dfeb072"

req = u.Request(BASE + "/api/operator/vio/overview?limit=10",
                headers={"X-Ops-Key": KEY})
data = json.loads(u.urlopen(req, timeout=20).read())

print("ok:", data.get("ok"))
print("companies:", len(data.get("companies", [])))
print()

for c in data.get("companies", []):
    print("─" * 70)
    print(f"company:        {c.get('company_name')!r}")
    print(f"intake_id:      {c.get('intake_id')}")
    print(f"stage:          {c.get('stage')!r}")
    print(f"stage_index:    {c.get('stage_index')}")
    print(f"stage_state:    {c.get('stage_state')!r}")
    print(f"state:          {c.get('state')!r}")
    print(f"urgency_score:  {c.get('urgency_score')}")
    print(f"days_in_stage:  {c.get('days_in_stage')}")
    print(f"attention:      {c.get('attention')}")
    print(f"quick_stats:    {c.get('quick_stats')}")
    print(f"timeline ({len(c.get('timeline', []))} segments):")
    for seg in c.get("timeline", []):
        print(f"  - {seg.get('type'):14s} status={seg.get('status'):10s} "
              f"label={(seg.get('label') or '')[:60]!r}")
