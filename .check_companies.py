import urllib.request
import json

req = urllib.request.Request(
    'https://jetfighter-compliance.onrender.com/api/operator/evidence-companies',
    headers={
        'User-Agent': 'curl',
        'X-Ops-Key': '939f0db78c714666a4a5686e751d13972b04975be65244d0a91841a38dfeb072'
    }
)
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read().decode())
companies = data.get('companies', []) if isinstance(data, dict) else data
print(f'Companies: {len(companies)}')
if companies:
    print(f'First: {companies[0].get("company_name", "?")} ({companies[0].get("intake_id", "?")})')
