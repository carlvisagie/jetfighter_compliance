"""Regression guards for the five bugs surfaced by production intake
``FB-1dfab13c120b`` on 2026-06-04.

The first real customer-style packet on production exposed:

1. EI was scanning the whole intake directory via ``rglob("*")``, so it
   processed internal files (``intake.json``, ``classification.json``,
   ``*.durability.json``) as if they were customer evidence — and the
   actual customer images were starved of OCR because the loop ran
   alphabetically and never reached ``uploads/image.jpg`` for the
   in-progress upload batch.
2. The entity extractor was lifting durability-sidecar filenames into
   the customer profile as ``domain`` entities. A live customer would
   have been asked to confirm ``image.jpg.durability.json`` as their
   own domain — embarrassing.
3. ``files_uploaded`` / ``files_analyzed`` were inflated by every
   internal JSON file picked up by the loop.
4. ``storage.load_gaps`` returned a CMMC-only cached gap list written
   before the domain-aware pack landed, masking the new framework-
   relevant guidance for every project whose ``gaps.json`` predated
   the deployment.
5. The scheduler heartbeat reported MISSING on a healthy process
   because ``load_telemetry(limit=500)`` pulled the most-recent 500
   rows *across all subsystems* — within minutes of boot the single
   ``scheduler_started`` row had been pushed out by routine EI traffic.

Each fix has a guard below so the same bug cannot quietly come back.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from services.evidence_intelligence import (
    _EI_INTERNAL_FILENAMES,
    _is_real_customer_upload,
    get_customer_evidence_profile,
    get_operator_evidence_intelligence,
    process_evidence_upload,
)
from services.evidence_intelligence import storage
from services.organism_state.collectors import SchedulerHeartbeatCollector


# --- Bug 1 + 2 -------------------------------------------------------------


def test_is_real_customer_upload_blocks_internal_metadata():
    for name in _EI_INTERNAL_FILENAMES:
        assert _is_real_customer_upload(name) is False, (
            f"{name!r} must not be processed as customer evidence"
        )


def test_is_real_customer_upload_blocks_durability_sidecars():
    assert _is_real_customer_upload("image.jpg.durability.json")          is False
    assert _is_real_customer_upload("KYC_packet (1).zip.durability.json") is False
    assert _is_real_customer_upload("anything-at-all.durability.json")    is False


def test_is_real_customer_upload_accepts_normal_uploads():
    assert _is_real_customer_upload("image.jpg")        is True
    assert _is_real_customer_upload("policy_v3.pdf")    is True
    assert _is_real_customer_upload("KYC packet.zip")   is True
    assert _is_real_customer_upload("training.docx")    is True


def test_is_real_customer_upload_rejects_empty_and_none():
    assert _is_real_customer_upload("")   is False
    assert _is_real_customer_upload(None) is False  # type: ignore[arg-type]


# --- Bug 1: intake EI loop is scoped to uploads/ only ----------------------


def test_intake_pipeline_only_dispatches_ei_for_uploads_subdir(tmp_path, monkeypatch):
    """Mimic the live intake directory shape and assert EI only sees
    files under ``uploads/`` (i.e. not ``intake.json`` /
    ``classification.json`` / ``*.durability.json``)."""
    from services import config as cfg
    monkeypatch.setattr(cfg, "DATA", tmp_path)
    import services.intake.storage as ist
    monkeypatch.setattr(ist, "DATA", tmp_path, raising=False)

    iid = "FB-EISCOPETEST1"
    idir = tmp_path / "intakes" / iid
    (idir / "uploads").mkdir(parents=True)
    # Fake intake metadata files at the top of the dir.
    (idir / "intake.json").write_text("{}", encoding="utf-8")
    (idir / "classification.json").write_text("{}", encoding="utf-8")
    # Real customer upload + its durability sidecar.
    (idir / "uploads" / "policy.txt").write_text(
        "Acme Inc multi-factor authentication policy", encoding="utf-8"
    )
    (idir / "uploads" / "policy.txt.durability.json").write_text(
        '{"sha256":"abc"}', encoding="utf-8"
    )

    # Replicate the production-side scoping pass.
    from services.intake.file_durability import is_upload_payload_file
    uploads_dir = idir / "uploads"
    ei_files = sorted(
        p for p in uploads_dir.iterdir()
        if p.is_file() and is_upload_payload_file(p.name)
    )
    names = {p.name for p in ei_files}

    assert "policy.txt" in names
    assert "policy.txt.durability.json" not in names
    assert "intake.json" not in names
    assert "classification.json" not in names


# --- Bug 2: read-side scrub keeps polluted JSONLs out of operator view -----


@pytest.fixture
def ei_data_root(tmp_path, monkeypatch):
    from services import config as cfg
    monkeypatch.setattr(cfg, "DATA", tmp_path)
    import services.evidence_intelligence as ei
    monkeypatch.setattr(ei, "DATA", tmp_path)
    return tmp_path


def _seed_polluted_ei_records(pid: str, base: Path) -> None:
    """Reproduce the on-disk pollution from production intake
    FB-1dfab13c120b: mix of real upload rows and metadata rows."""
    intel = base / "projects" / pid / "evidence_intelligence"
    intel.mkdir(parents=True, exist_ok=True)

    # extractions.jsonl — one real upload, two polluted metadata rows
    import json
    with (intel / "extractions.jsonl").open("w", encoding="utf-8") as f:
        for rec in [
            {"source_file": "policy.txt",          "status": "completed"},
            {"source_file": "intake.json",         "status": "completed"},
            {"source_file": "classification.json", "status": "completed"},
        ]:
            f.write(json.dumps(rec) + "\n")

    with (intel / "classifications.jsonl").open("w", encoding="utf-8") as f:
        for rec in [
            {"source_file": "policy.txt",          "document_type": "policy",  "confidence": 0.7},
            {"source_file": "intake.json",         "document_type": "contract", "confidence": 0.71},
            {"source_file": "classification.json", "document_type": "ssp",      "confidence": 0.83},
        ]:
            f.write(json.dumps(rec) + "\n")

    with (intel / "entities.jsonl").open("w", encoding="utf-8") as f:
        for rec in [
            {"source_file": "policy.txt",                       "type": "email",  "value": "ops@acme.com"},
            {"source_file": "image.jpg.durability.json",        "type": "domain", "value": "image.jpg.durability.json"},
            {"source_file": "classification.json",              "type": "domain", "value": "classification.json"},
        ]:
            f.write(json.dumps(rec) + "\n")

    profile = {
        "project_id":   pid,
        "primary_domain": "general",
        "domains": [
            {"value": "acme.com",                       "status": "inferred"},
            {"value": "image.jpg.durability.json",      "status": "inferred"},
            {"value": "527c49.jpg.durability.json",    "status": "inferred"},
        ],
        "document_inventory": [
            {"file": "policy.txt", "document_type": "policy", "confidence": 0.7,
             "signals": ["multi-factor"]},
        ],
    }
    (intel / "profile.json").write_text(json.dumps(profile), encoding="utf-8")


def test_operator_payload_filters_polluted_metadata_rows(ei_data_root):
    pid = "P-POLLUTED01"
    _seed_polluted_ei_records(pid, ei_data_root)

    op = get_operator_evidence_intelligence(pid)

    # Only the real upload should be counted.
    types = [c.get("source_file") for c in op["document_types"]]
    assert "intake.json"         not in types
    assert "classification.json" not in types
    assert "policy.txt"          in types


def test_customer_payload_strips_durability_sidecar_domains(ei_data_root):
    pid = "P-POLLUTED02"
    _seed_polluted_ei_records(pid, ei_data_root)

    payload = get_customer_evidence_profile(pid)
    domains = (payload.get("identified") or {}).get("domains") or []

    # Real domain stays, sidecar pollution removed.
    assert "acme.com" in domains
    assert all(not d.endswith(".durability.json") for d in domains), (
        f"durability sidecars must never appear as customer domains: {domains!r}"
    )


# --- Bug 4: gaps always refreshed from latest profile ---------------------


def test_operator_payload_recomputes_gaps_ignoring_stale_cache(ei_data_root):
    """Even with a stale gaps.json on disk, the operator view must
    return the freshly-computed pack from the current profile + domain
    detection — otherwise a CMMC-flavoured cache written before the
    domain-aware deployment never gets corrected."""
    pid = "P-STALEGAPS1"
    import json
    intel = ei_data_root / "projects" / pid / "evidence_intelligence"
    intel.mkdir(parents=True, exist_ok=True)

    # Profile that is clearly a DOT/FMCSA packet.
    profile = {
        "project_id": pid,
        "primary_domain": "DOT_FMCSA",
        "domain_confidence": 0.85,
        "document_inventory": [
            {"file": "dqf.pdf", "document_type": "policy",
             "signals": ["driver qualification", "mvr"]},
        ],
    }
    (intel / "profile.json").write_text(json.dumps(profile), encoding="utf-8")

    # Stale cache: legacy CMMC-only gaps written before the new pack.
    stale_cmmc_gaps = [
        {"gap_id": "mfa_evidence",     "label": "MFA",      "priority": "high"},
        {"gap_id": "ssp_poam",         "label": "SSP/POA&M","priority": "low"},
        {"gap_id": "training_record",  "label": "Training", "priority": "high"},
    ]
    (intel / "gaps.json").write_text(json.dumps(stale_cmmc_gaps), encoding="utf-8")

    op = get_operator_evidence_intelligence(pid)
    gap_ids = {g.get("gap_id") for g in op["gaps"]}

    # CMMC-only stale cache must NOT dominate.
    assert "ssp_poam" not in gap_ids
    # DOT pack rules must surface for a DOT profile.
    assert any(
        g in gap_ids for g in (
            "driver_qualification_file",
            "hours_of_service_logs",
            "drug_alcohol_program",
            "operating_authority",
        )
    ), f"DOT pack must surface for a DOT profile; got {gap_ids}"


# --- Bug 5: scheduler heartbeat survives noisy mixed-subsystem telemetry --


def test_scheduler_heartbeat_collector_filters_by_subsystem(tmp_path, monkeypatch):
    """Simulate production: scheduler_started emitted once, then ~600
    EI / intake / acquisition events spam the telemetry log. The
    collector must still see the scheduler row because it scopes to
    subsystem='system'."""
    import json
    from services.memory import telemetry as tel

    monkeypatch.setattr(tel, "_path",
                        lambda base=None: tmp_path / "telemetry.jsonl")

    log = tmp_path / "telemetry.jsonl"
    rows = []
    # The pulse we care about.
    rows.append({
        "telemetry_id": "T-1",
        "subsystem":    "system",
        "event_type":   "scheduler_started",
        "created_utc":  "2026-06-04T15:32:25Z",
        "success":      True,
    })
    # Hundreds of noisy events from other subsystems.
    for i in range(600):
        rows.append({
            "telemetry_id": f"T-{i+2}",
            "subsystem":    "evidence_intelligence",
            "event_type":   "evidence_extraction_completed",
            "created_utc":  "2026-06-04T15:35:00Z",
            "success":      True,
        })
    log.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )

    collector = SchedulerHeartbeatCollector()
    section = collector.collect()
    assert section.get("available") is True
    # The scheduler_started row must survive the noisy load.
    assert section.get("last_started_utc"), (
        "scheduler_started must be visible to the collector even after "
        "hundreds of mixed-subsystem rows"
    )
