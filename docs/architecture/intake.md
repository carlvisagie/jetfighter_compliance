# Intake — Architecture

**Owner:** Customer paperwork custody  
**Canonical detail:** [`../FORENSIC_INTEGRITY_ENGINE.md`](../FORENSIC_INTEGRITY_ENGINE.md), [`../KYC_UPLOAD_IMMUTABILITY_PROOF.md`](../KYC_UPLOAD_IMMUTABILITY_PROOF.md)

## Purpose

Receive, persist, hash-verify, and index customer files with forensic custody. Single canonical pipeline — no alternate queue or storage root.

## Inputs

- `POST /api/intake/upload`, customer session upload APIs
- Multipart files + manifest (`expected_file_count`, `batch_complete`)
- Durable root probe (`services/intake/durable_root.py`)

## Outputs

- `intakes/<FB-*>/uploads/*` on disk
- `intake.json`, `transaction_lifecycle.jsonl`, audit receipt
- Index JSONL, operator queue row
- Promotion copy to `projects/<id>/evidence/`
- Derived `evidence_registry.jsonl` (rebuilt, not authoritative)

## Dependencies

- `/var/data` mount (`KYC_DATA`)
- `services/intake/intake.py`, `integrity.py`, `proof_gate.py`, `reconcile.py`
- `services/durable_storage.py` production gate
- Integrity repair: `POST /api/operator/integrity/repair/{id}`

## Failure Modes

- Ephemeral disk → uploads refused (SEV-1)
- Proof gate failure → 500, integrity incident
- Multi-batch stale `expected` → metadata repair, not file deletion
- Concurrent upload race → retention may fail until reconcile/repair
