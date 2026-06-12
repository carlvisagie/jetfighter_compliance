"""Debug deep enrichment."""
import sys
sys.path.insert(0, '.')

import json
from datetime import datetime
import urllib.request
import urllib.error

company = 'KHEM PRECISION MACHINING LLC'

USASPENDING_AWARD_SEARCH = "https://api.usaspending.gov/api/v2/search/spending_by_award/"

# Test the exact payload
payload = {
    "filters": {
        "recipient_search_text": [company],
        "time_period": [
            {"start_date": "2018-01-01", "end_date": datetime.now().strftime("%Y-%m-%d")}
        ],
        "award_type_codes": ["A", "B", "C", "D"],
    },
    "fields": [
        "Award ID",
        "Recipient Name", 
        "Recipient UEI",
        "Award Amount",
        "Awarding Agency",
        "NAICS Code",
        "Start Date",
    ],
    "page": 1,
    "limit": 10,
    "sort": "Award Amount",
    "order": "desc",
}

print("Payload:")
print(json.dumps(payload, indent=2))
print()

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    USASPENDING_AWARD_SEARCH,
    data=data,
    headers={
        "Content-Type": "application/json",
        "User-Agent": "KeepYourContracts-Debug/1.0",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        awards = result.get("results", [])
        print(f"Awards found: {len(awards)}")
        if awards:
            print(json.dumps(awards[0], indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(f"Response: {e.read().decode('utf-8')}")
