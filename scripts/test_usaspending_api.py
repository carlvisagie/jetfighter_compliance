"""Test USASpending API to debug UEI acquisition."""
import httpx
import json
from datetime import datetime

def test_award_search():
    """Test the award search API."""
    url = 'https://api.usaspending.gov/api/v2/search/spending_by_award/'
    payload = {
        'filters': {
            'recipient_search_text': ['KHEM PRECISION MACHINING'],
            'time_period': [
                {'start_date': '2018-01-01', 'end_date': datetime.now().strftime('%Y-%m-%d')}
            ],
        },
        'fields': [
            'Recipient Name',
            'Recipient UEI',
            'Award Amount',
        ],
        'page': 1,
        'limit': 5,
        'sort': 'Award Amount',
        'order': 'desc',
    }
    
    print("Testing award search with httpx...")
    resp = httpx.post(url, json=payload, timeout=30)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        results = data.get('results', [])
        print(f"Results: {len(results)}")
        if results:
            print(json.dumps(results[0], indent=2))
    else:
        print(f"Error: {resp.text[:500]}")


def test_with_urllib():
    """Test with urllib to match production code."""
    import urllib.request
    
    url = 'https://api.usaspending.gov/api/v2/search/spending_by_award/'
    payload = {
        'filters': {
            'recipient_search_text': ['KHEM PRECISION MACHINING'],
            'time_period': [
                {'start_date': '2018-01-01', 'end_date': datetime.now().strftime('%Y-%m-%d')}
            ],
        },
        'fields': [
            'Recipient Name',
            'Recipient UEI',
            'Award Amount',
        ],
        'page': 1,
        'limit': 5,
        'sort': 'Award Amount',
        'order': 'desc',
    }
    
    print("\nTesting award search with urllib...")
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'KeepYourContracts-Test/1.0',
        },
        method='POST',
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            results = result.get('results', [])
            print(f"Status: 200")
            print(f"Results: {len(results)}")
            if results:
                print(json.dumps(results[0], indent=2))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(f"Response: {e.read().decode('utf-8')[:500]}")


if __name__ == '__main__':
    test_award_search()
    test_with_urllib()
