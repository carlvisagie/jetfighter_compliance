"""Debug full deep enrichment process."""
import sys
sys.path.insert(0, '.')

import json

from services.acquisition.usaspending_deep import (
    acquire_uei,
    get_award_profile_by_uei,
    get_award_profile_by_name_fallback,
    analyze_naics,
    assess_compliance_exposure,
)

company = 'KHEM PRECISION MACHINING LLC'

print("=== STEP 1: UEI Acquisition ===")
uei_result = acquire_uei(company)
print(f"UEI found: {uei_result.is_found()}")
print(f"UEI: {uei_result.uei}")
print(f"Location: {uei_result.location}")
print(f"Confidence: {uei_result.confidence}")

print("\n=== STEP 2: Award Profile ===")
if uei_result.uei:
    print(f"Calling get_award_profile_by_uei({uei_result.uei}, '{company}')")
    profile = get_award_profile_by_uei(uei_result.uei, company)
else:
    print(f"Calling get_award_profile_by_name_fallback('{company}')")
    profile = get_award_profile_by_name_fallback(company)

print(f"Success: {profile.success}")
print(f"Error: {profile.error}")
print(f"Contract count: {profile.contract_count}")
print(f"Total value: ${profile.total_contract_value:,.2f}")
print(f"DoD count: {profile.dod_award_count}")
print(f"DoD %: {profile.dod_percentage:.1f}")
print(f"NAICS codes: {profile.naics_codes}")
print(f"Primary NAICS: {profile.primary_naics}")
print(f"Most recent date: {profile.most_recent_award_date}")
print(f"Agencies: {profile.agencies[:3]}")

print("\n=== STEP 3: NAICS Analysis ===")
naics_intel = analyze_naics(profile.naics_codes, company)
print(f"Manufacturing: {naics_intel.is_manufacturing} (conf: {naics_intel.manufacturing_confidence})")
print(f"Aerospace: {naics_intel.is_aerospace} (conf: {naics_intel.aerospace_confidence})")
print(f"Defense: {naics_intel.is_defense} (conf: {naics_intel.defense_confidence})")

print("\n=== STEP 4: Compliance Exposure ===")
compliance = assess_compliance_exposure(
    dod_percentage=profile.dod_percentage,
    dod_award_count=profile.dod_award_count,
    is_manufacturing=naics_intel.is_manufacturing,
    is_defense=naics_intel.is_defense or profile.dod_award_count > 0,
    naics_codes=profile.naics_codes,
)
print(f"CMMC likelihood: {compliance.cmmc_likelihood:.2f}")
print(f"CMMC evidence: {compliance.cmmc_evidence}")
print(f"DFARS likelihood: {compliance.dfars_likelihood:.2f}")
print(f"DFARS evidence: {compliance.dfars_evidence}")

print("\n=== EXPECTED FIELDS TO ADD ===")
if profile.success and profile.contract_count > 0:
    print("contract_count: YES")
    print("contract_value: YES" if profile.total_contract_value > 0 else "contract_value: NO")
    print("award_recency: YES" if profile.most_recent_award_date else "award_recency: NO")
    print("agency_mix: YES" if profile.agencies else "agency_mix: NO")
    print("dod_exposure: YES" if profile.dod_award_count > 0 else "dod_exposure: NO")
    print("naics: YES" if profile.primary_naics else "naics: NO (null from API)")
    print("manufacturing_exposure: YES" if naics_intel.is_manufacturing else "manufacturing_exposure: from name inference")
    print("cmmc_likelihood: YES" if compliance.cmmc_likelihood > 0 else "cmmc_likelihood: NO")
    print("dfars_likelihood: YES" if compliance.dfars_likelihood > 0 else "dfars_likelihood: NO")
else:
    print(f"Profile failed: {profile.error}")
