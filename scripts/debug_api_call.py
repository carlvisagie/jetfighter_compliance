"""Debug the exact API call being made."""
import sys
sys.path.insert(0, '.')

import json
from datetime import datetime
import urllib.request
import urllib.error

company = 'KHEM PRECISION MACHINING LLC'
uei = 'K5CTDF3K3PL4'

USASPENDING_AWARD_SEARCH = "https://api.usaspending.gov/api/v2/search/spending_by_award/"

# This is the exact payload from get_award_profile_by_uei
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
        "Awarding Sub Agency",
        "Award Type",
        "Start Date",
        "End Date",
        "NAICS Code",
        "NAICS Description",
        "Place of Performance City",
        "Place of Performance State Code",
        "Description",
    ],
    "page": 1,
    "limit": 500,
    "sort": "Award Amount",
    "order": "desc",
}

print("Testing get_award_profile_by_uei payload...")
print(f"Payload length: {len(json.dumps(payload))} chars")

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    USASPENDING_AWARD_SEARCH,
    data=data,
    headers={
        "Content-Type": "application/json",
        "User-Agent": "KeepYourContracts-DeepEnrichment/1.0 (+https://compliance.keepyourcontracts.com; lawful-evidence-collection)",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        awards = result.get("results", [])
        print(f"SUCCESS! Awards found: {len(awards)}")
        if awards:
            print(f"First award UEI: {awards[0].get('Recipient UEI')}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    body = e.read().decode('utf-8')
    print(f"Response: {body}")
