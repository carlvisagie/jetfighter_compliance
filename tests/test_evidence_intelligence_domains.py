"""Regression guard: domain-aware gap detection.

Pinning the contract that came out of the 2026-06-04 forensic audit:

* A DOT/FMCSA carrier's evidence packet must surface DOT-specific gaps
  (Driver Qualification File, HOS / ELD, drug & alcohol program),
  *not* the legacy CMMC-only list.
* A CMMC packet must still surface CMMC-specific gaps (MFA, training,
  vulnerability scans, SSP/POA&M).
* A project with no domain signals must fall back to the universal
  baseline (asset inventory, vendor management, backup, IR) and not
  pretend it's CMMC.
* Gap satisfaction works two ways: by classified document_type and by
  text signal in the inventory blob.
* The operator and customer EI payloads expose ``primary_domain`` and
  ``domain_confidence`` so the UI can show framework-relevant guidance.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from services.evidence_intelligence import gaps as gaps_mod
from services.evidence_intelligence import (
    get_customer_evidence_profile,
    get_operator_evidence_intelligence,
    process_evidence_upload,
)
from services.evidence_intelligence import storage
from services.evidence_intelligence.domains import (
    detect_compliance_domain,
    rules_for_domain,
)


# --- domain detector --------------------------------------------------------


def test_detect_compliance_domain_dot_packet():
    profile = {
        "document_inventory": [
            {"file": "DQF_smith.pdf",     "document_type": "policy",
             "signals": ["driver qualification", "mvr", "dot physical"]},
            {"file": "eld_export_q1.csv", "document_type": "unknown",
             "signals": ["electronic logging", "hours of service"]},
        ],
        "compliance_references": [
            {"value": "49 CFR 391", "status": "inferred"},
        ],
    }
    result = detect_compliance_domain(profile)
    assert result.domain == "DOT_FMCSA"
    assert result.confidence > 0.4
    assert "DOT_FMCSA" in (result.signals or {})


def test_detect_compliance_domain_cmmc_packet():
    profile = {
        "document_inventory": [
            {"file": "ssp.pdf",  "document_type": "ssp",
             "signals": ["system security plan", "nist 800-171"]},
            {"file": "poam.pdf", "document_type": "poam",
             "signals": ["plan of action", "cui"]},
        ],
    }
    result = detect_compliance_domain(profile)
    assert result.domain == "CMMC"
    assert result.confidence > 0.4


def test_detect_compliance_domain_eu_dpp_packet():
    profile = {
        "document_inventory": [
            {"file": "dpp_registration.pdf", "document_type": "policy",
             "signals": ["digital product passport", "ESPR"]},
        ],
    }
    result = detect_compliance_domain(profile)
    assert result.domain == "EU_DPP"
    assert result.confidence > 0.4


def test_detect_compliance_domain_general_when_no_signals():
    profile = {
        "document_inventory": [
            {"file": "random.txt", "document_type": "unknown", "signals": []},
        ],
    }
    result = detect_compliance_domain(profile)
    assert result.domain == "general"
    assert result.confidence == 0.0


def test_rules_for_domain_includes_universal_pack():
    dot_rules = {r["gap_id"] for r in rules_for_domain("DOT_FMCSA")}
    # DOT-specific
    assert "driver_qualification_file"   in dot_rules
    assert "hours_of_service_logs"       in dot_rules
    # Universal (everyone needs these)
    assert "asset_inventory" in dot_rules
    assert "vendor_policy"   in dot_rules
    # CMMC-specific must NOT leak into a DOT pack
    assert "mfa_evidence" not in dot_rules
    assert "ssp_poam"     not in dot_rules


def test_rules_for_domain_cmmc_keeps_cmmc_pack():
    cmmc_rules = {r["gap_id"] for r in rules_for_domain("CMMC")}
    assert "mfa_evidence"          in cmmc_rules
    assert "training_record"       in cmmc_rules
    assert "ssp_poam"              in cmmc_rules
    assert "driver_qualification_file" not in cmmc_rules


# --- detect_gaps dispatch ---------------------------------------------------


def test_detect_gaps_dot_packet_returns_dot_gaps():
    profile = {
        "document_inventory": [
            {"file": "dqf_smith.pdf", "document_type": "policy",
             "signals": ["driver qualification", "mvr"]},
        ],
    }
    gaps = gaps_mod.detect_gaps(profile)
    gap_ids = {g.gap_id for g in gaps}
    # DOT pack must surface (whatever isn't satisfied by signals)
    assert "hours_of_service_logs" in gap_ids
    assert "dot_medical_exam"      in gap_ids or "driver_qualification_file" not in gap_ids
    # CMMC pack must NOT surface
    assert "ssp_poam"     not in gap_ids
    assert "mfa_evidence" not in gap_ids


def test_detect_gaps_text_signal_satisfies_rule():
    """A DOT carrier whose inventory mentions 'mvr' and 'driver qualification'
    should have the driver_qualification_file gap considered satisfied
    even though no document was classified as 'driver_qualification_file'."""
    profile = {
        "document_inventory": [
            {"file": "DQF.pdf", "document_type": "policy",
             "signals": ["driver qualification", "mvr", "road test"]},
        ],
    }
    gaps = gaps_mod.detect_gaps(profile, domain="DOT_FMCSA")
    gap_ids = {g.gap_id for g in gaps}
    assert "driver_qualification_file" not in gap_ids, (
        "Text signal 'driver qualification' should satisfy the DQF rule"
    )


def test_detect_gaps_explicit_domain_override():
    profile = {
        "document_inventory": [
            {"file": "random.txt", "document_type": "unknown", "signals": []},
        ],
    }
    # Explicitly force CMMC even though no signals would have detected it
    gaps = gaps_mod.detect_gaps(profile, domain="CMMC")
    gap_ids = {g.gap_id for g in gaps}
    assert "mfa_evidence" in gap_ids


def test_detect_gaps_general_fallback_returns_universal_only():
    profile = {"document_inventory": []}
    gaps = gaps_mod.detect_gaps(profile)  # auto-detects "general"
    gap_ids = {g.gap_id for g in gaps}
    # Universal rules surface
    assert {"asset_inventory", "vendor_policy", "backup_evidence",
            "incident_response"}.issubset(gap_ids)
    # No domain-specific rules surface
    assert "mfa_evidence"             not in gap_ids
    assert "driver_qualification_file" not in gap_ids
    assert "product_passport_registration" not in gap_ids


# --- end-to-end through processing pipeline --------------------------------


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


@pytest.fixture
def ei_root(tmp_path, monkeypatch):
    """Point EI storage and intake DATA at an isolated tmp directory.

    ``services.evidence_intelligence.storage`` re-imports DATA on every
    call via ``_data_root`` so monkeypatching ``services.config.DATA``
    is sufficient. The EI package-level ``DATA`` was bound at import
    time, so override that too for ``get_operator_evidence_intelligence``.
    """
    from services import config
    monkeypatch.setattr(config, "DATA", tmp_path)
    import services.evidence_intelligence as ei
    monkeypatch.setattr(ei, "DATA", tmp_path)
    yield tmp_path


def test_processing_pipeline_persists_dot_domain_on_profile(ei_root, tmp_path):
    pid = "P-DOTDOMAIN1"
    body = (
        "This is a Driver Qualification File for carrier XYZ Trucking LLC. "
        "USDOT number 123456. Medical examiner certificate expires 2026-12-31. "
        "Hours of service logs maintained via ELD. 49 CFR 391 compliance."
    )
    p = _write(tmp_path, "dqf_packet.txt", body)
    result = process_evidence_upload(pid, p, artifact_id="a-1")
    assert result.ok is True

    profile = storage.load_profile(pid)
    assert profile.get("primary_domain") == "DOT_FMCSA"
    assert profile.get("domain_confidence", 0) > 0.3

    op = get_operator_evidence_intelligence(pid)
    assert op["primary_domain"]    == "DOT_FMCSA"
    assert op["domain_confidence"] > 0.3
    gap_ids = {g.get("gap_id") for g in op["gaps"]}
    assert "ssp_poam" not in gap_ids   # CMMC-only should NOT surface
    assert any(g in gap_ids for g in (
        "hours_of_service_logs",
        "drug_alcohol_program",
        "operating_authority",
    )), f"DOT pack must surface its rules; got {gap_ids}"


def test_processing_pipeline_persists_cmmc_domain_on_profile(ei_root, tmp_path):
    pid = "P-CMMCDOM01"
    body = (
        "Acme Defense Contractor System Security Plan (SSP) covering NIST "
        "SP 800-171 controls for CUI handling. DFARS 252.204-7012 applies. "
        "POA&M attached for open gaps. CMMC Level 2 self-assessment."
    )
    p = _write(tmp_path, "ssp.txt", body)
    result = process_evidence_upload(pid, p, artifact_id="a-1")
    assert result.ok is True

    profile = storage.load_profile(pid)
    assert profile.get("primary_domain") == "CMMC"

    op = get_operator_evidence_intelligence(pid)
    assert op["primary_domain"] == "CMMC"
    gap_ids = {g.get("gap_id") for g in op["gaps"]}
    assert "driver_qualification_file" not in gap_ids
    # CMMC pack relevant gaps appear (whatever isn't already satisfied)
    assert any(g in gap_ids for g in (
        "mfa_evidence",
        "training_record",
        "vulnerability_evidence",
    ))


def test_customer_payload_exposes_primary_domain(ei_root, tmp_path):
    pid = "P-CUSTDOM01"
    body = (
        "Carrier ABC Trucking — DOT physical and MVR on file. "
        "USDOT registered. Hours of service ELD logs available."
    )
    p = _write(tmp_path, "carrier.txt", body)
    process_evidence_upload(pid, p, artifact_id="a-1")

    payload = get_customer_evidence_profile(pid)
    assert payload["primary_domain"]    == "DOT_FMCSA"
    assert payload["domain_confidence"] > 0
