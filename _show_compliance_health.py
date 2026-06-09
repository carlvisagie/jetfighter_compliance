"""Example compliance health output for PATCH 13A-1."""
from services.compliance_health import build_assessment
from services.compliance_health.registry import load_requirements
import json

print("=== COMPLIANCE HEALTH EXAMPLE (without SAM.gov API configured) ===\n")

# Load requirements
reqs = load_requirements()

print("Top 3 Requirements (SAM.gov related):")
for r in reqs[:3]:
    print(f"  {r.requirement_id}:")
    print(f"    Status: {r.status.value}")
    print(f"    Confidence: {r.confidence}")
    print(f"    Required: {r.required}")
    print(f"    Blocking: {r.blocking}")

# Build assessment
print("\nBuilding assessment for project 'EXAMPLE-001'...\n")
assessment = build_assessment("EXAMPLE-001")

print(f"Overall Status: {assessment.overall_status.value}")
print(f"Coverage: {assessment.verification_coverage_percent}%")
print(f"Missing Verifications: {len(assessment.missing_verifications)} requirements")
print(f"Blocking Failures: {len(assessment.blocking_failures)}")

print("\nMissing verifications:")
for missing_id in assessment.missing_verifications[:5]:
    req = next(r for r in reqs if r.requirement_id == missing_id)
    print(f"  - {req.name} ({missing_id})")

print("\nSample requirement (SAM Registration):")
sam_req = next(r for r in reqs if r.requirement_id == "sam_registration")
print(json.dumps(sam_req.model_dump(), indent=2))
