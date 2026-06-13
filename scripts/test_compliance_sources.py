"""Test if the failing source URLs are actually accessible."""
import httpx

FAILING_SOURCES = {
    "dod_cmmc": "https://www.ecfr.gov/current/title-32/subtitle-A/chapter-I/subchapter-G/part-170",
    "far": "https://acquisition.gov/far/",
    "cisa_advisories": "https://www.cisa.gov/news-events/cybersecurity-advisories",
    "eu_dpp_espr": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1781",
}

print("=" * 80)
print("TESTING UNREACHABLE SOURCE URLS")
print("=" * 80)

for source_id, url in FAILING_SOURCES.items():
    print(f"\n[{source_id}]")
    print(f"URL: {url}")
    
    try:
        headers = {
            "User-Agent": "KeepYourContracts-ComplianceIntel/1.0 (Compliance Monitoring; +https://keepyourcontracts.com)"
        }
        r = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        print(f"Status: {r.status_code}")
        if r.status_code >= 400:
            print(f"ERROR: {r.status_code}")
            print(f"Response: {r.text[:200]}")
    except httpx.TimeoutException:
        print("ERROR: Timeout")
    except Exception as e:
        print(f"ERROR: {str(e)[:100]}")

print("\n" + "=" * 80)
