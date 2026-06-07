# Evidence Intelligence — Architecture

**Owner:** Intake / compliance extraction  
**Canonical detail:** [`../EVIDENCE_INTELLIGENCE_LAYER.md`](../EVIDENCE_INTELLIGENCE_LAYER.md)

## Purpose

Extract, classify, and gap-detect customer uploads after intake. Feeds VIO KPIs and operator review — does not replace central memory or expert judgment.

## Inputs

- Files under `projects/<intake_id>/evidence/` (promoted from intake uploads)
- OCR runtime (`KYC_OCR_ENABLED`) when installed
- Domain packs (`services/evidence_intelligence/domains.py`)

## Outputs

- `projects/<id>/evidence_intelligence/*.jsonl`, `profile.json`, `gaps.json`
- `GET /api/operator/evidence-intelligence`
- Telemetry + `safe_write_after_evidence_intelligence` memory bridge
- Organism check `evidence_vs_files`

## Dependencies

- Intake promotion path (`services/intake/intake.py`)
- `services/evidence_intelligence/` package
- Optional: Tesseract/poppler (Dockerfile)
- Freshness sweep (`services/evidence_intelligence/freshness.py`)

## Failure Modes

- OCR unavailable → `pending_analysis` rows, not silent success
- Reprocess failure → review queue item, custody transaction event
- Profile pollution from sidecar files → scrub on read (defensive)
