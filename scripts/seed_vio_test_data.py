#!/usr/bin/env python3
"""
VIO 2.0 acceptance test data seeder.

Creates 5 realistic test companies in 5 different lifecycle states so that
VIO 2.0 can be validated as an awareness-at-a-glance instrument.

Run from workspace root:
    python scripts/seed_vio_test_data.py

To remove seed data later:
    python scripts/seed_vio_test_data.py --clean
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Workspace root on sys.path ─────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from services.config import DATA, PROJECTS  # noqa: E402

# ── Constants ──────────────────────────────────────────────────────────────────
INTAKES_ROOT = DATA / "intakes"
INDEX_JSONL   = INTAKES_ROOT / "index.jsonl"

SEED_TAG = "VIODEMO"  # prefix so we can clean up later

# ── Time helpers ───────────────────────────────────────────────────────────────
def ts(delta_hours: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=delta_hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# ── Company definitions ────────────────────────────────────────────────────────
# Each dict drives one complete seed sequence.
COMPANIES = [
    # ── 1. NEW INQUIRY ─────────────────────────────────────────────────────────
    {
        "intake_id":     f"FB-{SEED_TAG}001",
        "company":       "Apex Aerospace LLC",
        "email":         "compliance@apexaerospace.com",
        "review_status": "pending_review",
        "context":       "CMMC Level 2 readiness — DoD subcontract requirement.",
        "urgent":        False,
        "age_hours":     2,
        "evidence_files": [],  # No uploads yet — pure new state
        "project_id":    None,
    },

    # ── 2. WAITING ON CUSTOMER ─────────────────────────────────────────────────
    {
        "intake_id":     f"FB-{SEED_TAG}002",
        "company":       "Delta Manufacturing Corp",
        "email":         "it@deltamfg.com",
        "review_status": "pending_review",
        "context":       "DFARS compliance for prime contractor. Need NIST 800-171 gap analysis.",
        "urgent":        False,
        "age_hours":     18,
        "project_id":    f"P-{SEED_TAG}002",
        "evidence_files": [
            {
                "name": "delta_it_policy.txt",
                "content": """Delta Manufacturing Corp — IT Security Policy v2.1
Approved by: James Wilson, CISO
Date: March 12, 2024

1. PURPOSE
This policy establishes security requirements for Delta Manufacturing Corp
employees, contractors, and all systems handling Controlled Unclassified
Information (CUI) under DFARS 252.204-7012.

2. SCOPE
All information systems at Delta Manufacturing Corp including Azure cloud
workloads, on-premise servers at 4500 Industrial Blvd, Detroit MI 48201.

3. MULTI-FACTOR AUTHENTICATION
Multi-factor authentication (MFA) is mandatory for all user accounts.
Microsoft Entra ID enforces MFA via Microsoft Authenticator app.
Privileged accounts require hardware token (YubiKey).

4. ACCESS CONTROL
Access reviews conducted quarterly by IT Department.
Principle of least privilege enforced via Active Directory groups.

5. INCIDENT RESPONSE
Incident response procedures detailed in IR Plan v3.0 (separate document).
Contact: security@deltamfg.com | 313-555-0142

Compliance references: NIST SP 800-171, DFARS 252.204-7012, CMMC Level 2
""",
            },
        ],
    },

    # ── 3. GAP DETECTED ────────────────────────────────────────────────────────
    {
        "intake_id":     f"FB-{SEED_TAG}003",
        "company":       "Sigma Defense Solutions Inc",
        "email":         "carl@sigmadefense.com",
        "review_status": "pending_review",
        "context":       "ITAR compliance + CMMC L2. Dual-use tech. Multiple DoD contracts.",
        "urgent":        True,
        "age_hours":     36,
        "project_id":    f"P-{SEED_TAG}003",
        "evidence_files": [
            {
                "name": "sigma_vendor_agreements.txt",
                "content": """Sigma Defense Solutions Inc — Third Party Vendor Register
Updated: February 2024 | Owner: Operations Manager

ACTIVE VENDORS
==============
1. Microsoft Azure — Cloud infrastructure (CUI workloads)
   Contract ref: MSFT-ENT-2024-089
   ITAR exemption: EAR99

2. CrowdStrike Falcon — Endpoint detection and response
   Contract: CS-2024-SIGMA
   SOC 2 Type II certified

3. Cisco Secure — Network infrastructure
   Hardware maintenance agreement 2024-2026

4. Proofpoint — Email security and phishing simulation
   Annual subscription

5. AWS GovCloud — Backup workloads (east-us region)
   ITAR eligible environment

COMPLIANCE REFERENCES
====================
ITAR Part 120-130
DFARS 252.204-7012
NIST SP 800-171 Rev 2
CMMC Level 2

Contact: vendor-mgmt@sigmadefense.com | 703-555-0199
Address: 2200 Defense Way, Arlington VA 22201
""",
            },
            {
                "name": "sigma_asset_inventory.csv",
                "content": """Asset ID,Asset Type,Name,Location,Owner,OS,Last Patched
SA-001,Server,FS-PROD-01,Arlington DC,IT,Windows Server 2022,2024-02-15
SA-002,Server,FS-PROD-02,Arlington DC,IT,Windows Server 2022,2024-02-15
SA-003,Workstation,WS-CARL,Office,Carl Smith,Windows 11,2024-03-01
SA-004,Workstation,WS-JANE,Office,Jane Doe,Windows 11,2024-03-01
SA-005,Network,Cisco ASA 5516,Arlington DC,IT,ASA OS 9.18,2024-01-20
SA-006,Network,Cisco 9300 Switch,Arlington DC,IT,IOS-XE 17.9,2024-01-20
SA-007,Cloud,Azure Subscription,Azure East US,IT,N/A,Continuous
SA-008,Cloud,AWS GovCloud,AWS GovCloud East,IT,N/A,Continuous
""",
            },
        ],
    },

    # ── 4. PAYMENT REQUESTED ───────────────────────────────────────────────────
    {
        "intake_id":     f"FB-{SEED_TAG}004",
        "company":       "Theta Systems LLC",
        "email":         "president@thetasystems.com",
        "review_status": "approved",
        "context":       "ISO 27001 gap assessment + CMMC L1. Small defense supplier.",
        "urgent":        False,
        "age_hours":     72,
        "project_id":    f"P-{SEED_TAG}004",
        "evidence_files": [
            {
                "name": "theta_mfa_screenshot_description.txt",
                "content": """Theta Systems LLC — MFA Configuration Evidence
Exported from Microsoft 365 Admin Center
Date: January 15, 2024

MFA Status Report:
==================
Total users: 12
MFA enabled: 12 (100%)
MFA enforced: 12 (100%)
Method: Microsoft Authenticator (primary)
Backup: SMS (secondary)

Conditional Access Policy: "Require MFA for all users"
Policy state: Enabled
Policy conditions: All users, All cloud apps
Grant control: Require multi-factor authentication

Authentication methods registered:
- Microsoft Authenticator: 12 users
- SMS: 8 users
- FIDO2 Security Key: 2 users (executives)

Report generated by: Microsoft Entra ID (Azure Active Directory)
Tenant: thetasystems.onmicrosoft.com
""",
            },
            {
                "name": "theta_security_training.txt",
                "content": """Theta Systems LLC — Security Awareness Training Report
Platform: KnowBe4
Period: January 1 - December 31, 2023
Generated: January 5, 2024

TRAINING COMPLETION SUMMARY
============================
Assigned users: 12
Completed: 12 (100%)
Average score: 94.2%

Modules completed by all staff:
- NIST 800-171 Basics for Defense Contractors (100%)
- Phishing Awareness and Social Engineering (100%)
- CUI Handling and Marking (100%)
- Incident Reporting Procedures (100%)
- Password Security and MFA (100%)

Phishing simulation results:
- Q1: 8.3% click rate
- Q2: 5.1% click rate
- Q3: 3.2% click rate
- Q4: 1.7% click rate (industry avg 10-15%)

Contact: hr@thetasystems.com
CMMC reference: NIST SP 800-171 Control 3.2.1, 3.2.2
""",
            },
        ],
    },

    # ── 5. COMPLETED ───────────────────────────────────────────────────────────
    {
        "intake_id":     f"FB-{SEED_TAG}005",
        "company":       "Omega Compliance Group",
        "email":         "cto@omegacompliance.com",
        "review_status": "archived",
        "context":       "Full CMMC L2 + DFARS. Large defense prime. Engagement complete.",
        "urgent":        False,
        "age_hours":     168,  # 1 week ago
        "project_id":    f"P-{SEED_TAG}005",
        "evidence_files": [
            {
                "name": "omega_ssp_summary.txt",
                "content": """Omega Compliance Group — System Security Plan (SSP) Summary
Version: 3.1 | Classification: CUI
Author: ISSO | Date: December 2023

SYSTEM BOUNDARY
===============
Organization: Omega Compliance Group
System Name: Omega Defense Information System (ODIS)
System Owner: Chief Technology Officer
ISSO: Information Security Officer
Address: 1000 Compliance Ave, McLean VA 22102

SYSTEM CATEGORIZATION
====================
Confidentiality: High
Integrity: High
Availability: Moderate
CUI Categories: Defense, Export Controlled

IMPLEMENTED CONTROLS (NIST SP 800-171 Rev 2)
=============================================
Total controls: 110
Implemented: 110 (100%)
Compensating controls: 3
POA&M items: 0 (all resolved)

TECHNOLOGY STACK
================
Identity: Microsoft Entra ID with MFA enforced
Endpoint: CrowdStrike Falcon + Microsoft Defender
Email: Proofpoint Email Gateway
Network: Palo Alto Networks NGFW
Cloud: Azure GovCloud (FedRAMP High)
Backup: Veeam to Azure immutable storage
SIEM: Microsoft Sentinel

COMPLIANCE STATUS
=================
CMMC Level 2: Ready for C3PAO assessment
DFARS 252.204-7012: Fully implemented
NIST SP 800-171 Rev 2: 110/110 controls implemented
ISO 27001: Certified (cert expires 2025-06)

Last assessment: November 2023 by independent assessor
Next scheduled assessment: November 2024
""",
            },
            {
                "name": "omega_poam.txt",
                "content": """Omega Compliance Group — Plan of Action & Milestones (POA&M)
As of December 31, 2023 | Status: ALL ITEMS CLOSED

POA&M Summary
=============
Total items opened (lifetime): 14
Items closed: 14
Items open: 0
Items overdue: 0

Recently closed items:
----------------------
POA&M-012: Encrypt all CUI at rest — CLOSED 2023-11-30
  Action: Implemented BitLocker and Azure SSE
  Evidence: Encryption policy + screenshot

POA&M-013: SIEM coverage for all endpoints — CLOSED 2023-12-01
  Action: Deployed Microsoft Sentinel for all 47 endpoints
  Evidence: Sentinel dashboard export

POA&M-014: Annual access review — CLOSED 2023-12-15
  Action: Completed Q4 2023 access review
  Evidence: Signed access review report

System is fully remediated.
CMMC Level 2 self-attestation complete.
C3PAO assessment scheduled: Q1 2024
""",
            },
        ],
    },
]


# ── Seeding functions ──────────────────────────────────────────────────────────

def _write_intake(company: dict) -> None:
    intake_id = company["intake_id"]
    created   = ts(company["age_hours"])
    status    = company["review_status"]

    intake_dir = INTAKES_ROOT / intake_id
    intake_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir = intake_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    files_meta = []
    for ef in company.get("evidence_files") or []:
        fpath = uploads_dir / ef["name"]
        fpath.write_text(ef["content"], encoding="utf-8")
        files_meta.append({
            "name": ef["name"],
            "size": len(ef["content"].encode()),
            "ext": Path(ef["name"]).suffix,
            "uploaded_at_utc": created,
        })

    intake_rec = {
        "intake_id":      intake_id,
        "created_at_utc": created,
        "updated_at_utc": ts(max(0, company["age_hours"] - 1)),
        "status":         status,
        "review_status":  status,
        "company":        company["company"],
        "email":          company["email"],
        "phone":          "",
        "context":        company.get("context", ""),
        "deadline":       "",
        "urgent":         company.get("urgent", False),
        "files":          files_meta,
        "file_count":     len(files_meta),
        "total_bytes":    sum(f["size"] for f in files_meta),
        "_seed_tag":      SEED_TAG,
    }
    if company.get("project_id"):
        intake_rec["project_id"] = company["project_id"]

    (intake_dir / "intake.json").write_text(
        json.dumps(intake_rec, indent=2), encoding="utf-8"
    )

    # Index entry
    index_entry = {
        "intake_id":      intake_id,
        "created_at_utc": created,
        "status":         status,
        "company":        company["company"],
        "email":          company["email"],
        "urgent":         company.get("urgent", False),
        "file_count":     len(files_meta),
        "committed":      True,
        "_seed_tag":      SEED_TAG,
    }
    with INDEX_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(index_entry) + "\n")

        print(f"  [OK] Intake {intake_id} ({company['company']}) -> {status}")


def _write_project(company: dict) -> None:
    pid = company.get("project_id")
    if not pid:
        return

    pdir = PROJECTS / pid
    (pdir / "evidence").mkdir(parents=True, exist_ok=True)
    (pdir / "communications").mkdir(parents=True, exist_ok=True)

    meta = {
        "project_id":          pid,
        "order_id":            company["intake_id"],
        "canonical_intake_id": company["intake_id"],
        "customer": {
            "email": company["email"],
            "name":  company["company"],
        },
        "skus":       ["UPLOAD-FIRST"],
        "created_at": ts(company["age_hours"]).replace("-", "").replace(":", "").replace("Z", "Z"),
        "status":     "initiated",
        "_seed_tag":  SEED_TAG,
    }
    (pdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Copy evidence files to project evidence dir
    intake_dir = INTAKES_ROOT / company["intake_id"]
    for ef in company.get("evidence_files") or []:
        src  = intake_dir / "uploads" / ef["name"]
        dest = pdir / "evidence" / ef["name"]
        if src.exists():
            dest.write_bytes(src.read_bytes())

    print(f"  [OK] Project {pid} ({company['company']})")


def _run_evidence_intelligence(company: dict) -> None:
    pid = company.get("project_id")
    if not pid:
        return
    if not company.get("evidence_files"):
        return

    from services.evidence_intelligence import process_evidence_upload

    ev_dir = PROJECTS / pid / "evidence"
    for ef in company.get("evidence_files") or []:
        fpath = ev_dir / ef["name"]
        if not fpath.exists():
            print(f"  [WARN] Evidence file missing: {fpath}")
            continue
        result = process_evidence_upload(pid, fpath)
        print(f"  [OK] EI processed {ef['name']} -> status={result.status}, "
              f"entities={result.entities_extracted}, gaps={result.gaps_detected}")

    # For the waiting company: force a confirmation_needed state by ensuring
    # at least one company_name_candidate with status=inferred exists
    # (it will be inferred naturally from extraction — no manual override needed)


def _confirm_all_entities(pid: str, label: str) -> None:
    """Mark all inferred entities as confirmed so needs_confirmation returns empty."""
    try:
        from services.evidence_intelligence import storage
        profile = storage.load_profile(pid)
        changed = 0
        for key in ("company_name_candidates", "emails", "domains", "technologies",
                    "vendors", "people", "phones", "addresses", "compliance_refs"):
            for item in profile.get(key) or []:
                if item.get("status") in ("inferred", "conflicting", "unsure"):
                    item["status"] = "confirmed"
                    changed += 1
        storage.write_profile(pid, profile)
        print(f"  [OK] {changed} entities confirmed for {label} ({pid})")
    except Exception as e:
        print(f"  [WARN] Could not confirm entities for {label}: {e}")


def _set_confirmed_entities_for_payment(company: dict) -> None:
    """Mark extracted entities as confirmed for the payment company — they are done."""
    pid = company.get("project_id")
    if not pid or company["review_status"] != "approved":
        return
    try:
        from services.evidence_intelligence import storage
        profile = storage.load_profile(pid)
        # Mark all inferred items as confirmed to clear confirmation_needed
        for key in ("company_name_candidates", "emails", "domains", "technologies"):
            for item in profile.get(key) or []:
                if item.get("status") in ("inferred", "conflicting"):
                    item["status"] = "confirmed"
        storage.write_profile(pid, profile)
        print(f"  [OK] Entities confirmed for approved company {pid}")
    except Exception as e:
        print(f"  [WARN] Could not confirm entities: {e}")


def seed() -> None:
    print("\n" + "=" * 55)
    print("  VIO 2.0 -- Test Data Seeder")
    print("=" * 55)
    print(f"  DATA root: {DATA}")
    print(f"  PROJECTS root: {PROJECTS}")
    print()

    INTAKES_ROOT.mkdir(parents=True, exist_ok=True)

    for i, company in enumerate(COMPANIES, 1):
        print(f"[{i}/5] {company['company']} → target state: {_target_state(company)}")
        _write_intake(company)
        _write_project(company)
        _run_evidence_intelligence(company)
        # Sigma (gap): confirm entities so state becomes "gap" not "waiting"
        if "Sigma" in company["company"]:
            _confirm_all_entities(company["project_id"], company["company"])
        # Omega (complete) and Theta (payment): confirm everything
        _set_confirmed_entities_for_payment(company)
        print()

    print("=" * 55)
    print("  Seed complete. Open /ui/vio.html to validate.")
    print("=" * 55 + "\n")
    _print_expected_vio_states()


def _target_state(company: dict) -> str:
    status = company["review_status"]
    if status == "archived":
        return "complete    (green glow)"
    if status == "approved":
        return "payment     (green pulse)"
    files = company.get("evidence_files") or []
    if not files:
        return "new         (grey orb)"
    # Has files — depends on whether EI will produce confirmation_needed or gaps
    name = company["company"]
    if "Delta" in name:
        return "waiting     (amber pulse — confirmation needed)"
    if "Sigma" in name:
        return "gap         (amber flicker — missing MFA, training, SSP)"
    return "active      (blue)"


def _print_expected_vio_states():
    print("  Expected VIO display:")
    print()
    print("  [OO] Omega Compliance Group  ---[intake]--[upload]--[done]  COMPLETE (green)")
    print("  [TT] Theta Systems LLC       ---[intake]--[upload]--[pay]   PAYMENT  (green pulse)")
    print("  [SS] Sigma Defense Solutions ---[intake]--[upload]--[gap]   GAP      (amber flicker)")
    print("  [DD] Delta Manufacturing     ---[intake]--[upload]--[wait]  WAITING  (amber pulse)")
    print("  [AA] Apex Aerospace LLC      ---[intake]                    NEW      (grey)")
    print()
    print("  Acceptance: operator can identify each state in < 3 seconds.")
    print()


def clean() -> None:
    """Remove all seed data."""
    print(f"\nCleaning seed data (tag={SEED_TAG})...")
    removed = 0

    # Remove intake directories
    if INTAKES_ROOT.exists():
        for d in INTAKES_ROOT.iterdir():
            if d.is_dir() and SEED_TAG in d.name:
                import shutil as _sh
                _sh.rmtree(d)
                removed += 1
                print(f"  [OK] Removed {d}")

    # Purge seed lines from index
    if INDEX_JSONL.exists():
        lines = [
            ln for ln in INDEX_JSONL.read_text(encoding="utf-8").splitlines()
            if SEED_TAG not in ln
        ]
        INDEX_JSONL.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
        print(f"  [OK] Purged {SEED_TAG} entries from index.jsonl")

    # Remove project directories
    if PROJECTS.exists():
        for d in PROJECTS.iterdir():
            if d.is_dir() and SEED_TAG in d.name:
                import shutil as _sh
                _sh.rmtree(d)
                removed += 1
                print(f"  [OK] Removed project {d}")

    print(f"  Done. {removed} directories removed.\n")


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    else:
        seed()
