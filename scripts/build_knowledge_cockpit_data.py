#!/usr/bin/env python3
"""Build canonical knowledge_cockpit JSON from in-repo seed definitions (no runtime E: paths)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "knowledge_cockpit"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


CONCEPTS = [
    {
        "id": "cmmc",
        "term": "CMMC",
        "aliases": ["Cybersecurity Maturity Model Certification", "CMMC certification"],
        "category": "framework",
        "operational_meaning": (
            "CMMC is the DoD contractor cybersecurity gate: it proves your environment "
            "meets a defined maturity level before you handle federal contract information. "
            "Think of it like an airworthiness program for your IT — not a one-time checklist, "
            "but demonstrated control and evidence over time."
        ),
        "why_it_matters": "Primes and agencies increasingly require CMMC (or equivalent) before award or flowdown. Without it, revenue stops.",
        "evidence_examples": ["SSP excerpt", "POA&M", "assessment results", "SPRS submission record"],
        "common_mistakes": [
            "Buying tools before scoping FCI vs CUI",
            "Treating CMMC as IT-only instead of contracts + operations",
            "Confusing readiness conversation with certified assessment",
        ],
        "related_ids": ["cmmc-level-1", "cmmc-level-2", "nist-800-171", "sprs-score", "c3pao"],
    },
    {
        "id": "cmmc-level-1",
        "term": "CMMC Level 1",
        "aliases": ["CMMC L1", "Level 1 CMMC"],
        "category": "framework",
        "operational_meaning": (
            "Level 1 is the entry bar for Federal Contract Information (FCI): basic safeguarding "
            "of contractor information systems. Like securing the hangar — locks, visitor rules, "
            "basic hygiene — not the full classified-material vault."
        ),
        "why_it_matters": "Many small subcontractors only need L1, but still must show practices and evidence.",
        "evidence_examples": ["Access control policy", "MFA screenshots", "employee security awareness"],
        "common_mistakes": ["Assuming L1 means no documentation", "Ignoring flowdown from prime"],
        "related_ids": ["fci", "cmmc", "access-control", "mfa"],
    },
    {
        "id": "cmmc-level-2",
        "term": "CMMC Level 2",
        "aliases": ["CMMC L2", "Level 2 CMMC"],
        "category": "framework",
        "operational_meaning": (
            "Level 2 aligns with NIST SP 800-171 for Controlled Unclassified Information (CUI). "
            "This is the aircraft logbook level: documented controls, owners, configuration, logs, "
            "and proof you operate them — not just policies on paper."
        ),
        "why_it_matters": "Most defense supply-chain pressure lands here. Primes ask for SSP, POA&M, and assessment path.",
        "evidence_examples": ["SSP", "POA&M", "audit logs", "incident response plan", "configuration baseline"],
        "common_mistakes": [
            "Scoping CUI boundary too wide or too narrow",
            "POA&M without owners and dates",
            "Evidence scattered across email instead of a defensible pack",
        ],
        "related_ids": ["cui", "nist-800-171", "ssp", "poam", "sprs-score", "c3pao"],
    },
    {
        "id": "dfars-7012",
        "term": "DFARS 252.204-7012",
        "aliases": ["DFARS 7012", "252.204-7012"],
        "category": "regulation",
        "operational_meaning": (
            "The contract clause that pulls NIST 800-171 requirements into your award and "
            "requires incident reporting, assessment, and system security plan obligations when you handle CUI."
        ),
        "why_it_matters": "If this clause is in your contract, compliance is contractual — not optional marketing.",
        "evidence_examples": ["Executed contract flowdown", "SSP", "incident reporting procedure"],
        "common_mistakes": ["Signing flowdowns without reading 7012", "No 72-hour incident reporting process"],
        "related_ids": ["nist-800-171", "cui", "ssp", "incident-response", "flowdown"],
    },
    {
        "id": "dfars-7021",
        "term": "DFARS 252.204-7021",
        "aliases": ["DFARS 7021", "Cybersecurity Maturity Model Certification clause"],
        "category": "regulation",
        "operational_meaning": (
            "Requires contractors to have a current CMMC status (or affirmation path) in SPRS "
            "at time of award for applicable acquisitions."
        ),
        "why_it_matters": "Drives the CMMC Level requirement into procurement — you must know your level before bidding.",
        "evidence_examples": ["SPRS score entry", "CMMC status letter", "POA&M if interim"],
        "common_mistakes": ["Bidding without checking SPRS status", "Confusing self-assessment with certification"],
        "related_ids": ["sprs-score", "cmmc", "cmmc-level-2"],
    },
    {
        "id": "nist-800-171",
        "term": "NIST SP 800-171",
        "aliases": ["NIST 800-171", "800-171", "SP 800-171"],
        "category": "framework",
        "operational_meaning": (
            "The control catalog for protecting CUI on non-federal systems — 110+ practices "
            "grouped by families (access, audit, config, etc.). Your SSP maps how you meet each."
        ),
        "why_it_matters": "This is the technical backbone of CMMC Level 2 and most vendor security questionnaires.",
        "evidence_examples": ["Control implementation statements", "POA&M", "assessment checklist"],
        "common_mistakes": ["Checkbox SSP with no operational evidence", "Ignoring shared responsibility with MSP"],
        "related_ids": ["cui", "ssp", "poam", "control", "assessment"],
    },
    {
        "id": "sprs-score",
        "term": "SPRS score",
        "aliases": ["SPRS", "Supplier Performance Risk System", "NIST score SPRS"],
        "category": "artifact",
        "operational_meaning": (
            "The DoD system where you record your NIST 800-171 self-assessment score (and CMMC status). "
            "Like filing your inspection readiness declaration — primes can see it."
        ),
        "why_it_matters": "Primes verify subcontractor posture before award. Wrong or missing score blocks deals.",
        "evidence_examples": ["SPRS screenshot", "Score calculation worksheet", "POA&M tied to gaps"],
        "common_mistakes": ["Maximum score claim without evidence", "Never updating after environment change"],
        "related_ids": ["nist-800-171", "dfars-7021", "poam"],
    },
    {
        "id": "ssp",
        "term": "SSP",
        "aliases": ["System Security Plan", "system security plan"],
        "category": "artifact",
        "operational_meaning": (
            "The SSP is the aircraft logbook for your security environment: what exists, how it is "
            "configured, who owns it, and how each NIST control is satisfied. Assessors read this first."
        ),
        "why_it_matters": "Without an SSP you cannot defend your posture to primes, insurers, or C3PAOs.",
        "evidence_examples": ["SSP document", "Network diagram", "Asset inventory", "Control narratives"],
        "common_mistakes": [
            "Generic template never tailored to real systems",
            "SSP version drift from production",
            "Missing shared responsibility for cloud/MSP",
        ],
        "related_ids": ["nist-800-171", "poam", "control", "evidence", "configuration-management"],
    },
    {
        "id": "poam",
        "term": "POA&M",
        "aliases": ["POAM", "Plan of Action and Milestones", "plan of action"],
        "category": "artifact",
        "operational_meaning": (
            "Your honest gap list: what is not fully met yet, who fixes it, by when, and with what evidence. "
            "Like open maintenance items on an aircraft — better owned than hidden."
        ),
        "why_it_matters": "Primes accept interim posture if POA&M is credible. Missing POA&M reads as denial.",
        "evidence_examples": ["POA&M spreadsheet", "Ticket IDs", "Remediation evidence"],
        "common_mistakes": ["Perpetual open items with no dates", "POA&M disconnected from SSP controls"],
        "related_ids": ["ssp", "assessment", "nist-800-171"],
    },
    {
        "id": "cui",
        "term": "CUI",
        "aliases": ["Controlled Unclassified Information"],
        "category": "concept",
        "operational_meaning": (
            "Government-created or handled information that requires safeguarding under law/regulation — "
            "not classified, but not public. Your CUI boundary defines which systems and data fall under 800-171."
        ),
        "why_it_matters": "Wrong boundary means wrong scope, wrong costs, and failed assessments.",
        "evidence_examples": ["CUI marking examples", "Data flow diagram", "Contract CUI clauses"],
        "common_mistakes": ["Treating all customer data as CUI", "No marking or handling procedure"],
        "related_ids": ["fci", "nist-800-171", "cmmc-level-2"],
    },
    {
        "id": "fci",
        "term": "FCI",
        "aliases": ["Federal Contract Information"],
        "category": "concept",
        "operational_meaning": (
            "Information provided by or generated for the government under contract that is not public. "
            "Lower bar than CUI — CMMC Level 1 / FAR 52.204-21 basic safeguarding."
        ),
        "why_it_matters": "Determines whether you need L1-only vs full 800-171 / L2 program.",
        "evidence_examples": ["Contract deliverable list", "Basic safeguarding policy"],
        "common_mistakes": ["Assuming no government data means no FCI", "Ignoring email with contract attachments"],
        "related_ids": ["cmmc-level-1", "cui"],
    },
    {
        "id": "mfa",
        "term": "MFA",
        "aliases": ["multi-factor authentication", "2FA", "two-factor"],
        "category": "control",
        "operational_meaning": (
            "Proving identity with two factors before access — like badge plus PIN at the flight line. "
            "Customers and primes ask for MFA on email, VPN, and admin consoles."
        ),
        "why_it_matters": "Top vendor questionnaire ask; weak MFA is an instant finding.",
        "evidence_examples": ["IdP MFA policy", "Conditional access screenshot", "User enrollment report"],
        "common_mistakes": ["MFA on email only but not admins", "SMS-only MFA for privileged accounts"],
        "related_ids": ["access-control", "vendor-questionnaire", "evidence"],
    },
    {
        "id": "access-control",
        "term": "Access control",
        "aliases": ["AC", "identity and access"],
        "category": "control",
        "operational_meaning": "Who can access what, when, and how access is approved, reviewed, and revoked.",
        "why_it_matters": "Most findings and breaches trace to access — not missing policies.",
        "evidence_examples": ["User roster", "Joiner/mover/leaver procedure", "Privileged access review"],
        "common_mistakes": ["Shared admin accounts", "No periodic access review"],
        "related_ids": ["mfa", "audit-logs", "policy"],
    },
    {
        "id": "audit-logs",
        "term": "Audit logs",
        "aliases": ["logging", "audit trail", "SIEM"],
        "category": "control",
        "operational_meaning": (
            "Tamper-aware records of who did what on systems — chain-of-custody for IT events. "
            "You must collect, protect, and review them."
        ),
        "why_it_matters": "Assessors and incident response depend on logs. 'We would know' without logs fails.",
        "evidence_examples": ["Log retention policy", "Sample log export", "Review ticket"],
        "common_mistakes": ["Logs disabled to save cost", "No time sync (NTP)"],
        "related_ids": ["incident-response", "evidence"],
    },
    {
        "id": "incident-response",
        "term": "Incident response",
        "aliases": ["IR", "security incident", "breach response"],
        "category": "control",
        "operational_meaning": (
            "Documented steps when something goes wrong: detect, contain, report (including DFARS timelines), recover."
        ),
        "why_it_matters": "7012 reporting obligations are contractual. Chaos costs contracts.",
        "evidence_examples": ["IR plan", "Tabletop notes", "Reporting contact tree"],
        "common_mistakes": ["No 72-hour DoD reporting process", "IR plan never tested"],
        "related_ids": ["dfars-7012", "policy", "procedure"],
    },
    {
        "id": "configuration-management",
        "term": "Configuration management",
        "aliases": ["CM", "baseline configuration"],
        "category": "control",
        "operational_meaning": "Known-good builds for systems; changes tracked and approved — like approved modifications to aircraft.",
        "why_it_matters": "Drift creates invisible risk and failed assessments.",
        "evidence_examples": ["Baseline images", "Change tickets", "Inventory"],
        "common_mistakes": ["Shadow IT outside inventory", "No change approval for cloud tenants"],
        "related_ids": ["ssp", "control", "evidence"],
    },
    {
        "id": "vendor-questionnaire",
        "term": "Vendor questionnaire",
        "aliases": ["security questionnaire", "customer security questionnaire", "SIG", "CAIQ"],
        "category": "operational",
        "operational_meaning": (
            "A customer or prime sends a spreadsheet of security questions. "
            "You answer with policies, screenshots, and evidence — often under deadline."
        ),
        "why_it_matters": "Revenue gate for SaaS and subcontractors. Slow or vague answers kill deals.",
        "evidence_examples": ["Completed questionnaire", "Evidence pack", "Exception register"],
        "common_mistakes": [
            "Answering 'yes' without evidence",
            "Reinventing answers each time instead of a evidence library",
        ],
        "related_ids": ["evidence", "policy", "prime-contractor", "security-questionnaire"],
    },
    {
        "id": "security-questionnaire",
        "term": "Security questionnaire",
        "aliases": ["cyber insurance questionnaire", "supplier security assessment"],
        "category": "operational",
        "operational_meaning": "Same family as vendor questionnaires — may come from insurer, prime, or enterprise customer.",
        "why_it_matters": "Often the first signal a small business is under compliance burden without knowing CMMC by name.",
        "evidence_examples": ["SIG Lite answers", "Policy PDFs", "MFA proof"],
        "common_mistakes": ["Copy-paste from outdated year", "Ignoring insurance follow-up questions"],
        "related_ids": ["vendor-questionnaire", "evidence", "mfa"],
    },
    {
        "id": "evidence",
        "term": "Evidence",
        "aliases": ["proof", "artifacts", "compliance evidence"],
        "category": "concept",
        "operational_meaning": (
            "Artifacts that show a control is real: screenshots, exports, logs, tickets, signed policies. "
            "Chain-of-custody matters — who collected it and when."
        ),
        "why_it_matters": "Assessors trust evidence, not assertions. Upload-first onboarding exists to capture messy real packs.",
        "evidence_examples": ["Screenshots", "Policy PDFs", "Log excerpts", "Training completions"],
        "common_mistakes": ["Stale screenshots", "Evidence from wrong tenant/environment"],
        "related_ids": ["policy", "procedure", "ssp", "vendor-questionnaire"],
    },
    {
        "id": "policy",
        "term": "Policy",
        "aliases": ["security policy", "information security policy"],
        "category": "artifact",
        "operational_meaning": "Management intent — what you commit to do. Must match what operators actually do.",
        "why_it_matters": "Questionnaires always ask for policies first; mismatch with practice is a finding.",
        "evidence_examples": ["Approved policy PDF", "Annual review record", "Exception register"],
        "common_mistakes": ["Generic template with wrong company name", "Policy without owner or review date"],
        "related_ids": ["procedure", "evidence", "control"],
    },
    {
        "id": "procedure",
        "term": "Procedure",
        "aliases": ["SOP", "standard operating procedure"],
        "category": "artifact",
        "operational_meaning": "Step-by-step how work is done — turns policy into repeatable operations.",
        "why_it_matters": "Assessors ask 'show me how' — procedures are the bridge.",
        "evidence_examples": ["SOP document", "Completed checklist", "Training record"],
        "common_mistakes": ["Procedures that reference retired tools", "No version control"],
        "related_ids": ["policy", "evidence"],
    },
    {
        "id": "control",
        "term": "Control",
        "aliases": ["security control", "safeguard"],
        "category": "concept",
        "operational_meaning": "A specific requirement you satisfy (technical or administrative) — unit of SSP and assessments.",
        "why_it_matters": "Language of NIST, CMMC, and questionnaires — map customer asks to controls.",
        "evidence_examples": ["Control matrix", "Implementation statement", "Test result"],
        "common_mistakes": ["Implementing tools without mapping to control IDs"],
        "related_ids": ["nist-800-171", "assessment", "evidence"],
    },
    {
        "id": "assessment",
        "term": "Assessment",
        "aliases": ["security assessment", "compliance assessment", "audit"],
        "category": "operational",
        "operational_meaning": "Structured evaluation of controls against a standard — self, C3PAO, or customer audit.",
        "why_it_matters": "Defines what evidence must exist and at what rigor.",
        "evidence_examples": ["Assessment report", "Assessor notes", "Remediation list"],
        "common_mistakes": ["Confusing internal gap review with certification"],
        "related_ids": ["c3pao", "poam", "ssp"],
    },
    {
        "id": "c3pao",
        "term": "C3PAO",
        "aliases": ["CMMC Third-Party Assessment Organization", "C3PA"],
        "category": "operational",
        "operational_meaning": "Authorized assessor for CMMC certification — external validation, not self-attestation.",
        "why_it_matters": "Required path for CMMC certificate at applicable levels.",
        "evidence_examples": ["Assessment plan", "Certificate", "Scope letter"],
        "common_mistakes": ["Booking C3PAO before SSP/scope stable"],
        "related_ids": ["cmmc-level-2", "assessment"],
    },
    {
        "id": "prime-contractor",
        "term": "Prime contractor",
        "aliases": ["prime", "prime contractor"],
        "category": "operational",
        "operational_meaning": "The main contract holder flowing requirements down to you — often sends questionnaires and flowdown clauses.",
        "why_it_matters": "Most small business burden arrives as prime paperwork, not direct DoD contact.",
        "evidence_examples": ["Flowdown clause", "Supplier portal invite", "Questionnaire"],
        "common_mistakes": ["Signing flowdown without compliance review"],
        "related_ids": ["subcontractor", "flowdown", "vendor-questionnaire"],
    },
    {
        "id": "subcontractor",
        "term": "Subcontractor",
        "aliases": ["sub", "tier 2 supplier"],
        "category": "operational",
        "operational_meaning": "You in the supply chain — inheriting requirements from primes.",
        "why_it_matters": "Defines your operational reality: questionnaires, MFA asks, documentation deadlines.",
        "evidence_examples": ["Subcontract", "Supplier onboarding portal", "CMMC ask email"],
        "common_mistakes": ["Assuming prime will 'handle' compliance for you"],
        "related_ids": ["prime-contractor", "flowdown", "cmmc"],
    },
    {
        "id": "flowdown",
        "term": "Flowdown",
        "aliases": ["flow-down", "contract flowdown", "clause flowdown"],
        "category": "operational",
        "operational_meaning": "Contract clauses passed from prime to sub — including DFARS and cybersecurity terms.",
        "why_it_matters": "Your legal obligation often originates here, not from reading FAR yourself.",
        "evidence_examples": ["Executed subcontract", "Clause list", "Compliance attestation"],
        "common_mistakes": ["Missing flowdown in file", "Attesting without evidence"],
        "related_ids": ["dfars-7012", "prime-contractor", "subcontractor"],
    },
]

RELATIONSHIPS = [
    {"from": "cmmc-level-2", "to": "nist-800-171", "relation": "implements"},
    {"from": "cmmc-level-2", "to": "cui", "relation": "protects"},
    {"from": "cmmc-level-1", "to": "fci", "relation": "protects"},
    {"from": "cmmc", "to": "cmmc-level-1", "relation": "includes"},
    {"from": "cmmc", "to": "cmmc-level-2", "relation": "includes"},
    {"from": "dfars-7012", "to": "nist-800-171", "relation": "requires"},
    {"from": "dfars-7021", "to": "sprs-score", "relation": "requires"},
    {"from": "ssp", "to": "nist-800-171", "relation": "documents"},
    {"from": "poam", "to": "ssp", "relation": "remediates_gaps_in"},
    {"from": "vendor-questionnaire", "to": "evidence", "relation": "requests"},
    {"from": "vendor-questionnaire", "to": "mfa", "relation": "often_requires"},
    {"from": "vendor-questionnaire", "to": "policy", "relation": "often_requires"},
    {"from": "prime-contractor", "to": "vendor-questionnaire", "relation": "sends"},
    {"from": "flowdown", "to": "dfars-7012", "relation": "may_include"},
    {"from": "c3pao", "to": "cmmc-level-2", "relation": "assesses"},
    {"from": "sprs-score", "to": "nist-800-171", "relation": "declares_posture_for"},
]


SOURCES = [
    {
        "title": "NIST SP 800-171 Rev.3 (Final)",
        "publisher": "NIST CSRC",
        "url": "https://csrc.nist.gov/pubs/sp/800/171/r3/final",
        "scope": "CUI baseline",
        "type": "Publication",
    },
    {
        "title": "NIST SP 800-171A Rev.3 (Assessment)",
        "publisher": "NIST CSRC",
        "url": "https://csrc.nist.gov/pubs/sp/800/171/a/r3/final",
        "scope": "Assessment procedures",
        "type": "Publication",
    },
    {
        "title": "NIST SP 800-53 Rev.5 (Controls)",
        "publisher": "NIST CSRC",
        "url": "https://csrc.nist.gov/pubs/sp/800/53/r5/final",
        "scope": "Controls",
        "type": "Publication",
    },
    {
        "title": "EU AI Act — Regulation (EU) 2024/1689 (OJ)",
        "publisher": "EUR-Lex",
        "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
        "scope": "AI governance",
        "type": "Regulation",
    },
    {
        "title": "GDPR — Regulation (EU) 2016/679 (OJ)",
        "publisher": "EUR-Lex",
        "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
        "scope": "Data protection",
        "type": "Regulation",
    },
    {
        "title": "CISA KEV Catalog",
        "publisher": "CISA",
        "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "scope": "Threats",
        "type": "Portal",
    },
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "generated_utc": _utc(),
        "concept_count": len(CONCEPTS),
        "concepts": CONCEPTS,
    }
    (OUT / "concepts.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "relationships.json").write_text(
        json.dumps({"version": 1, "generated_utc": _utc(), "edges": RELATIONSHIPS}, indent=2),
        encoding="utf-8",
    )
    (OUT / "authoritative_sources.json").write_text(
        json.dumps({"version": 1, "generated_utc": _utc(), "sources": SOURCES}, indent=2),
        encoding="utf-8",
    )
    for name in ("operator_learning.jsonl", "recent_lookups.jsonl"):
        p = OUT / name
        if not p.exists():
            p.write_text("", encoding="utf-8")
    print(f"Wrote {len(CONCEPTS)} concepts to {OUT / 'concepts.json'}")


if __name__ == "__main__":
    main()
