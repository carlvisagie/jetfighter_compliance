#!/usr/bin/env python3
"""
VIO 2.0 live production seeder.

Creates 5 realistic test companies on the live Render instance.
Uses public intake upload endpoint to create intakes, then operator
API to advance each to the required lifecycle state.

Usage:
    python scripts/seed_vio_live.py             # seed + verify
    python scripts/seed_vio_live.py --check     # verify VIO only
    python scripts/seed_vio_live.py --clean     # list seed intakes

Production: https://jetfighter-compliance.onrender.com
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx not installed.  pip install httpx")
    sys.exit(1)

# Production-Is-The-Only-Truth contract: no --target / --env / --local allowed.
# See docs/PRODUCTION_IS_THE_ONLY_TRUTH.md and scripts/_prod_only.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _prod_only import (  # noqa: E402
    PRODUCTION_BASE_URL,
    PRODUCTION_FALLBACK_URL,
    reject_target_flag,
)
reject_target_flag()

# ── Config ─────────────────────────────────────────────────────────────────────
# Bound to production only. Keep the Render fallback for the legacy --check path
# below, but neither can be overridden by a CLI flag.
BASE_URL = PRODUCTION_FALLBACK_URL
ENV_FILE = Path(__file__).resolve().parent.parent / ".ops_env"
SEED_TAG = "VIODEMO"   # marker in company name so we can find them later


def _load_password() -> str:
    pwd = os.getenv("OPS_PASSWORD", "")
    if pwd:
        return pwd
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPS_PASSWORD="):
                return line.split("=", 1)[1].strip()
    sys.exit(f"ERROR: OPS_PASSWORD not found in env or {ENV_FILE}")


OPS_PASSWORD = _load_password()

# ── Session ────────────────────────────────────────────────────────────────────
_SESSION_COOKIES: dict = {}


def _authenticate() -> dict:
    global _SESSION_COOKIES
    if _SESSION_COOKIES:
        return _SESSION_COOKIES
    resp = httpx.post(
        f"{BASE_URL}/api/ops/login",
        json={"password": OPS_PASSWORD},
        timeout=20,
        follow_redirects=True,
    )
    if resp.status_code not in (200, 201):
        sys.exit(f"Login failed {resp.status_code}: {resp.text[:300]}")
    _SESSION_COOKIES = dict(resp.cookies)
    print(f"  [OK] Operator session established")
    return _SESSION_COOKIES


# ── Evidence file content ──────────────────────────────────────────────────────
EVIDENCE: dict[str, str] = {
    # ── Delta Manufacturing — waiting on customer confirmation ─────────────────
    "delta_it_policy.txt": """\
Delta Manufacturing Corp -- IT Security Policy v2.1
Approved by: James Wilson, CISO | Date: March 12, 2024

PURPOSE: This policy establishes security requirements for Delta Manufacturing Corp
employees handling CUI under DFARS 252.204-7012.

SCOPE: All systems at Delta Manufacturing Corp including Azure cloud workloads
and on-premise servers at 4500 Industrial Blvd, Detroit MI 48201.

MULTI-FACTOR AUTHENTICATION
Multi-factor authentication (MFA) is mandatory for all user accounts.
Microsoft Entra ID enforces MFA via Microsoft Authenticator app.

ACCESS CONTROL
Access reviews conducted quarterly. Principle of least privilege enforced
via Active Directory groups.

Contact: security@deltamfg.com | 313-555-0142
Compliance: NIST SP 800-171, DFARS 252.204-7012, CMMC Level 2
""",

    # ── Sigma Defense — gap detected ───────────────────────────────────────────
    "sigma_vendor_register.txt": """\
Sigma Defense Solutions Inc -- Third Party Vendor Register
Updated: February 2024 | Owner: Operations Manager

ACTIVE VENDORS
1. Microsoft Azure -- Cloud infrastructure (CUI workloads)
   ITAR exemption: EAR99
2. CrowdStrike Falcon -- Endpoint detection and response
   SOC 2 Type II certified
3. Cisco Secure -- Network infrastructure
4. Proofpoint -- Email security and phishing simulation
5. AWS GovCloud -- Backup workloads

COMPLIANCE: ITAR Part 120-130, DFARS 252.204-7012, NIST SP 800-171 Rev 2, CMMC Level 2

Contact: vendor-mgmt@sigmadefense.com | 703-555-0199
Address: 2200 Defense Way, Arlington VA 22201
""",

    "sigma_asset_inventory.csv": """\
Asset ID,Type,Name,Location,Owner,OS,Last Patched
SA-001,Server,FS-PROD-01,Arlington DC,IT,Windows Server 2022,2024-02-15
SA-002,Workstation,WS-Engineer,Office,Carl Smith,Windows 11,2024-03-01
SA-003,Network,Cisco ASA 5516,Arlington DC,IT,ASA OS 9.18,2024-01-20
SA-004,Cloud,Azure Subscription,Azure East US,IT,N/A,Continuous
SA-005,Cloud,AWS GovCloud,AWS GovCloud East,IT,N/A,Continuous
""",

    # ── Theta Systems — payment requested ──────────────────────────────────────
    "theta_mfa_evidence.txt": """\
Theta Systems LLC -- MFA Configuration Evidence
Exported from Microsoft 365 Admin Center | Date: January 15, 2024

MFA Status: 12/12 users enrolled (100%)
Method: Microsoft Authenticator (primary), SMS (backup)
Conditional Access Policy: "Require MFA for all users" -- ENABLED
Tenant: thetasystems.onmicrosoft.com
""",

    "theta_training_records.txt": """\
Theta Systems LLC -- Security Awareness Training Report
Platform: KnowBe4 | Period: Jan 1 - Dec 31, 2023

Completion: 12/12 users (100%) | Average score: 94.2%
Modules: NIST 800-171 Basics, Phishing Awareness, CUI Handling, Incident Reporting
Phishing simulation Q4: 1.7% click rate (industry avg 10-15%)

CMMC reference: NIST SP 800-171 Control 3.2.1, 3.2.2
""",

    # ── Omega Compliance — completed ───────────────────────────────────────────
    "omega_ssp_summary.txt": """\
Omega Compliance Group -- System Security Plan (SSP) Summary
Version: 3.1 | Classification: CUI | Date: December 2023
Address: 1000 Compliance Ave, McLean VA 22102

CONTROLS (NIST SP 800-171 Rev 2): 110/110 implemented. POA&M items: 0.

TECHNOLOGY STACK:
Identity: Microsoft Entra ID with MFA enforced
Endpoint: CrowdStrike Falcon + Microsoft Defender
Email: Proofpoint Email Gateway
Network: Palo Alto Networks NGFW
Cloud: Azure GovCloud (FedRAMP High)
SIEM: Microsoft Sentinel

COMPLIANCE: CMMC Level 2 ready, DFARS 252.204-7012 implemented, ISO 27001 certified.
""",

    "omega_poam.txt": """\
Omega Compliance Group -- Plan of Action & Milestones (POA&M)
As of December 31, 2023 | Status: ALL ITEMS CLOSED

Total opened: 14 | Closed: 14 | Open: 0 | Overdue: 0
CMMC Level 2 self-attestation complete.
C3PAO assessment scheduled: Q1 2024.
""",
}

# ── Company pipeline ───────────────────────────────────────────────────────────
COMPANIES: list[dict] = [
    {
        "company":        f"Apex Aerospace LLC [{SEED_TAG}]",
        "email":          "compliance@apexaerospace-demo.com",
        "context":        "CMMC Level 2 readiness. DoD subcontract requirement.",
        "target_state":   "new",
        "evidence":       [],
        "operator_action": None,
        "confirm_entities": False,
    },
    {
        "company":        f"Delta Manufacturing Corp [{SEED_TAG}]",
        "email":          "it@deltamfg-demo.com",
        "context":        "DFARS compliance. NIST 800-171 gap analysis.",
        "target_state":   "waiting",
        "evidence":       ["delta_it_policy.txt"],
        "operator_action": None,
        "confirm_entities": False,   # Leave as inferred -> waiting state
    },
    {
        "company":        f"Sigma Defense Solutions Inc [{SEED_TAG}]",
        "email":          "carl@sigmadefense-demo.com",
        "context":        "ITAR + CMMC L2. Dual-use tech. Multiple DoD contracts.",
        "target_state":   "gap",
        "evidence":       ["sigma_vendor_register.txt", "sigma_asset_inventory.csv"],
        "operator_action": None,
        "confirm_entities": True,   # Confirm -> no waiting -> gap state
    },
    {
        "company":        f"Theta Systems LLC [{SEED_TAG}]",
        "email":          "president@thetasystems-demo.com",
        "context":        "ISO 27001 assessment + CMMC L1. Small defense supplier.",
        "target_state":   "payment_pending",
        "evidence":       ["theta_mfa_evidence.txt", "theta_training_records.txt"],
        "operator_action": "approve_review",
        "confirm_entities": True,
    },
    {
        "company":        f"Omega Compliance Group [{SEED_TAG}]",
        "email":          "cto@omegacompliance-demo.com",
        "context":        "Full CMMC L2 + DFARS. Large defense prime. Engagement complete.",
        "target_state":   "complete",
        "evidence":       ["omega_ssp_summary.txt", "omega_poam.txt"],
        "operator_action": "archive",
        "confirm_entities": True,
    },
]


# ── Upload helpers ─────────────────────────────────────────────────────────────

def _upload_files(
    cookies: dict,
    company: str,
    email: str,
    context: str,
    evidence_files: list[str],
) -> tuple[str, str]:
    """
    Upload first evidence file to create the intake, return (intake_id, token).
    Subsequent files are uploaded with the returned intake_id + token.
    If no evidence, upload a minimal placeholder so the intake is created.
    """
    file_list = list(evidence_files)
    placeholder_used = False
    if not file_list:
        file_list = ["_context.txt"]
        placeholder_used = True

    intake_id = ""
    token     = ""

    for idx, filename in enumerate(file_list):
        if filename == "_context.txt":
            content = f"New inquiry: {company}\n{context}\n"
        else:
            content = EVIDENCE[filename]
        file_bytes = content.encode("utf-8")

        form_data: dict[str, str] = {}
        if idx == 0:
            form_data = {"company": company, "email": email, "context": context}
        else:
            form_data = {"intake_id": intake_id, "token": token}

        files = {"files": (filename, file_bytes, "text/plain")}

        resp = httpx.post(
            f"{BASE_URL}/api/intake/upload",
            data=form_data,
            files=files,
            cookies=cookies,
            timeout=30,
            follow_redirects=True,
        )
        if resp.status_code not in (200, 201):
            print(f"    [ERROR] Upload {filename} -> {resp.status_code}: {resp.text[:300]}")
            return "", ""

        data = resp.json()
        if idx == 0:
            intake_id = str(data.get("intake_id") or "")
            token     = str(data.get("token") or data.get("upload_token") or "")
            if not intake_id:
                print(f"    [ERROR] No intake_id in response: {json.dumps(data)[:300]}")
                return "", ""
            print(f"    [OK] Intake created: {intake_id}")
        else:
            print(f"    [OK] Uploaded {filename}")

        time.sleep(0.3)

    return intake_id, token


def _apply_operator_action(cookies: dict, intake_id: str, action: str) -> None:
    resp = httpx.post(
        f"{BASE_URL}/api/operator/intake/action",
        json={"intake_id": intake_id, "action": action},
        cookies=cookies,
        timeout=20,
        follow_redirects=True,
    )
    if resp.status_code not in (200, 201):
        print(f"    [WARN] Action {action} -> {resp.status_code}: {resp.text[:200]}")
    else:
        print(f"    [OK] Status -> {action}")


def _get_project_id(cookies: dict, intake_id: str) -> str:
    """Kick off a project so evidence intelligence can attach."""
    resp = httpx.post(
        f"{BASE_URL}/api/operator/intake/action",
        json={"intake_id": intake_id, "action": "kickoff_project"},
        cookies=cookies,
        timeout=20,
        follow_redirects=True,
    )
    if resp.status_code not in (200, 201):
        return ""
    data = resp.json()
    return str(data.get("project_id") or "")


def _confirm_entities(cookies: dict, project_id: str) -> None:
    """Mark all inferred entities confirmed so needs_confirmation is empty."""
    resp = httpx.get(
        f"{BASE_URL}/api/operator/evidence-intelligence",
        params={"project_id": project_id},
        cookies=cookies,
        timeout=20,
        follow_redirects=True,
    )
    if resp.status_code != 200:
        print(f"    [WARN] EI fetch -> {resp.status_code}")
        return

    ei = resp.json()
    items = ei.get("confirmation_needed") or []
    if not items:
        print(f"    [INFO] No confirmation_needed items for {project_id}")
        return

    confirmed = 0
    for item in items:
        field = item.get("field") or ""
        value = item.get("value") or ""
        if not field or value is None:
            continue
        r2 = httpx.post(
            f"{BASE_URL}/api/customer/evidence/confirm",
            json={"project_id": project_id, "field": field,
                  "value": str(value), "action": "confirmed"},
            cookies=cookies,
            timeout=15,
            follow_redirects=True,
        )
        if r2.status_code == 200:
            confirmed += 1
    print(f"    [OK] Confirmed {confirmed}/{len(items)} entities for {project_id}")


# ── Main seed routine ──────────────────────────────────────────────────────────

def seed() -> None:
    print("\n" + "=" * 60)
    print("  VIO 2.0 -- Live Production Seeder")
    print(f"  Target: {BASE_URL}")
    print("=" * 60 + "\n")

    cookies = _authenticate()

    results = []

    for i, company in enumerate(COMPANIES, 1):
        name = company["company"]
        print(f"[{i}/5] {name}")
        print(f"  Target state: {company['target_state']}")

        intake_id, token = _upload_files(
            cookies,
            company["company"],
            company["email"],
            company["context"],
            company["evidence"],
        )
        if not intake_id:
            print(f"  [SKIP] Could not create intake\n")
            continue

        project_id = ""

        # Companies with evidence + confirmation/gaps need a project ID
        if company.get("confirm_entities") or company["operator_action"] in ("approve_review", "archive"):
            time.sleep(1)
            project_id = _get_project_id(cookies, intake_id)
            if project_id:
                print(f"    [OK] Project: {project_id}")
            else:
                print(f"    [INFO] No project created (kickoff may need manual trigger)")

        if company.get("confirm_entities") and project_id:
            time.sleep(1.5)
            _confirm_entities(cookies, project_id)

        if company["operator_action"]:
            time.sleep(0.5)
            _apply_operator_action(cookies, intake_id, company["operator_action"])

        results.append({
            "company": name,
            "intake_id": intake_id,
            "project_id": project_id,
            "target_state": company["target_state"],
        })
        print()

    print("=" * 60)
    print("  Seeding complete. Summary:")
    for r in results:
        print(f"  [{r['target_state']:15}] {r['company'][:40]} -> {r['intake_id']}")
    print(f"\n  Open: {BASE_URL}/ui/vio.html")
    print("=" * 60 + "\n")


# ── VIO check ──────────────────────────────────────────────────────────────────

def check_vio() -> None:
    print(f"\nVerifying VIO at {BASE_URL}/api/operator/vio/overview ...")
    cookies = _authenticate()
    resp = httpx.get(
        f"{BASE_URL}/api/operator/vio/overview",
        cookies=cookies,
        timeout=20,
        follow_redirects=True,
    )
    if resp.status_code != 200:
        print(f"  [ERROR] {resp.status_code}: {resp.text[:300]}")
        return

    data = resp.json()
    companies = data.get("companies") or []
    health    = data.get("organism_health") or {}

    print(f"  [OK] VIO API: {len(companies)} companies visible\n")
    print(f"  {'STATE':<18} COMPANY")
    print(f"  {'-'*18} {'-'*35}")
    for c in companies:
        state = c.get("state", "?")
        cname = c.get("company_name", "?")
        print(f"  {state:<18} {cname[:50]}")

    print(f"\n  Health score: {health.get('score', '?')}")
    states_found = {c.get("state") for c in companies}
    required     = {"new", "waiting", "gap", "payment_pending", "complete"}
    missing      = required - states_found
    if missing:
        print(f"\n  [WARN] Missing states: {missing}")
        print(f"  Acceptance test: PARTIAL")
    else:
        print(f"\n  [OK] All 5 required states visible.")
        print(f"  Acceptance test: PASS")
    print()


# ── Clean (list only) ──────────────────────────────────────────────────────────

def clean() -> None:
    print(f"\nListing seed intakes at {BASE_URL} (tag={SEED_TAG}) ...")
    cookies = _authenticate()
    resp = httpx.get(
        f"{BASE_URL}/api/operator/intake/queue",
        params={"limit": 100, "include_archived": "true"},
        cookies=cookies,
        timeout=20,
        follow_redirects=True,
    )
    if resp.status_code != 200:
        print(f"  [ERROR] {resp.status_code}: {resp.text[:200]}")
        return
    queue = resp.json().get("queue") or []
    seed_rows = [r for r in queue if SEED_TAG in (r.get("company") or "")]
    print(f"  Found {len(seed_rows)} seed intakes:")
    for r in seed_rows:
        print(f"    {r['intake_id']} | {r['company'][:50]} | {r['review_status']}")
    print()


if __name__ == "__main__":
    if "--check" in sys.argv:
        check_vio()
    elif "--clean" in sys.argv:
        clean()
    else:
        seed()
        time.sleep(2)
        check_vio()
