import urllib.request
import json

req = urllib.request.Request(
    'https://jetfighter-compliance.onrender.com/api/operator/vio/overview?limit=10',
    headers={
        'User-Agent': 'curl',
        'X-Ops-Key': '939f0db78c714666a4a5686e751d13972b04975be65244d0a91841a38dfeb072'
    }
)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode())
    companies = data.get('companies', [])
    print(f'OK: {len(companies)} companies')
    if companies:
        first = companies[0]
        print(f'  First: {first.get("company_name", "?")}')
        print(f'  Stage: {first.get("stage_state", "?")}')
except Exception as e:
    print(f'ERROR: {e}')
