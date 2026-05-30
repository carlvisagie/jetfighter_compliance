# KYC Upload Immutability Proof

**Date:** 2026-05-30  
**Repo:** [carlvisagie/jetfighter_compliance](https://github.com/carlvisagie/jetfighter_compliance)  
**Production:** https://compliance.keepyourcontracts.com

---

## Canonical statement

**A successful upload cannot disappear without a SEV-1 forensic incident.**

Customer-visible success (`customer_may_show_success=true`, `proof_gate_passed=true`) is returned only after a synchronous proof gate verifies the intake is immediately discoverable on durable disk, in the index, operator queue/archive, retention-check, file list, and download/view paths.

---

## Root cause (Carl 13-file incident)

| Factor | Finding |
|--------|---------|
| **Symptom** | UI showed persisted/verified; production boot reported `dirs=0 files=0` |
| **Primary cause** | Upload HTTP success was decoupled from post-write discoverability proof — durability hash check passed in-process but fleet visibility was not gated before customer success |
| **Ephemeral disk risk** | Without explicit `KYC_DATA` pointing at Render persistent disk (`/var/data`), uploads land in container-local storage and vanish on redeploy |
| **Missing live proof** | Boot status used startup snapshot only; no live disk scan endpoint for post-boot verification |
| **Single copy** | Canonical uploads existed but no mandatory quarantine mirror or proof-gate incident on visibility failure |

---

## Architecture fix

### 1. Upload success proof gate (`services/intake/proof_gate.py`)

After durability verification and state commit, `require_upload_proof_gate()` verifies:

- Live disk scan file count ≥ verified count
- Index row present
- Queue or archive visibility
- Retention-check passes (hashes + disk count)
- Operator file list resolves all files as accessible
- Per-file download/view path resolution
- Quarantine mirror written under `{KYC_DATA}/intake_quarantine/{intake_id}/`

On any failure: HTTP 500, `X-KYC-Error-Code: upload_proof_gate_failed`, SEV-1 `upload_proof_gate_failed` incident, organism telemetry — **never customer success**.

Success response includes: `proof_gate_passed`, `data_root`, `write_path`, `live_scan_confirmed`, `queue_or_archive_visible`, `retention_visible`, `file_access_verified`, `verified_file_count`.

### 2. Dual durable records

| Copy | Path |
|------|------|
| Canonical | `{KYC_DATA}/intakes/{id}/uploads/` |
| Audit manifest | `{KYC_DATA}/intakes/{id}/intake_audit.json` |
| Quarantine mirror | `{KYC_DATA}/intake_quarantine/{id}/uploads/` + `quarantine_manifest.json` |

Reconstruction order: disk → audit receipt → quarantine manifest → transaction log → forensic recovery.

### 3. Live endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/ops/boot-status/live` | Ops session | Live disk scan + forensic proof + upload pipeline severity (not cached boot snapshot) |
| `GET /api/operator/intake/raw-disk-scan` | Ops session | Live filesystem inventory; optional `?intake_id=` |

Cached boot snapshot remains at `GET /api/ops/boot-status` (explicitly labeled `scan_type: boot_snapshot`).

### 4. Startup reconciliation

`scan_retention_at_startup()` now runs `live_disk_scan()`, `build_live_boot_status()`, and `detect_cockpit_zero_after_recent_success()`. Sets `healthy: false` and emits SEV-1 when index/disk disagree or live boot status is critical.

### 5. Forensic engine owns failure

- Integrity incidents block fleet proof (`build_integrity_proof ok=false` when incidents exist)
- COTE upload node severity forced red when forensic proof fails
- Delete protection (`services/intake/delete_protection.py`) — unreviewed uploads cannot be deleted without explicit retention policy + audit + operator auth

### 6. Archive does not hide files

Archive changes `review_status` only. Files remain on disk; raw-disk-scan, retention-check, and download/view remain available.

---

## Destructive test matrix

**File:** `tests/test_upload_immutability.py` (21 tests)

| Scenario | Result |
|----------|--------|
| 1 file visible everywhere | PASS |
| 13 files visible everywhere | PASS |
| Index write fail → no success | PASS |
| Queue cannot see → no success | PASS |
| Retention cannot see → no success | PASS |
| File list cannot resolve → no success | PASS |
| Restart after upload keeps files | PASS |
| Simulated redeploy keeps files | PASS |
| Archive keeps files accessible | PASS |
| Corrupt file → incident | PASS |
| Delete intake.json → reconstruct | PASS |
| Delete index → reconstruct | PASS |
| Delete audit receipt → incident | PASS |
| Delete uploaded file → incident | PASS |
| Wrong KYC_DATA root fails loudly | PASS |
| Safe mode cannot hide uploads | PASS |
| Cockpit zero while pending on disk → SEV-1 | PASS |
| Live boot scan reflects post-boot uploads | PASS |

**Full suite:** `706 passed` (2026-05-30 local run)

---

## Production proof status

| Step | Status | Notes |
|------|--------|-------|
| Deploy with proof gate | **Pending deploy** | Requires push + Render auto-deploy |
| Public 13-file upload | **Blocked without deploy** | Gate ships in this changeset |
| `GET /api/ops/boot-status/live` | **Requires OPS_PASSWORD** | Ops-auth protected; prior investigation (`prod_upload_investigation.json`) returned 401 |
| `GET /api/operator/intake/raw-disk-scan` | **Requires OPS_PASSWORD** | Same |
| Restart/redeploy retention | **Requires OPS_PASSWORD + deploy** | Manual verification post-deploy |

### Ops-auth gap (honest)

Production operator endpoints require valid `OPS_PASSWORD` session cookie or `X-Ops-Key`. Automated production proof from CI/agent without Carl's credentials can verify:

- `GET /healthz` / `GET /health/ready` (public)
- Public upload responses include `proof_gate_passed` fields after deploy

Cannot verify raw-disk-scan, queue, retention-check, or live boot status without operator auth.

### Post-deploy verification checklist (Carl)

1. Deploy commit to Render `kyc-backend`
2. Login: `POST /api/ops/login` with production `OPS_PASSWORD`
3. Upload 13 PDFs via `/ui/founding-beta` or `POST /api/intake/upload`
4. Confirm response: `proof_gate_passed=true`, `verified_file_count=13`
5. `GET /api/operator/intake/raw-disk-scan?intake_id={id}` → 13 files
6. `GET /api/operator/intake/retention-check/{id}` → counts match, hashes match
7. `GET /api/operator/intake/{id}/files` → 13 accessible documents
8. Download all 13 via `/files/{name}/download`
9. `GET /api/ops/boot-status/live` → `upload_files` includes 13, `status` not `critical`
10. Trigger Render restart → repeat steps 5–9
11. Archive intake → files still on raw-disk-scan and downloadable

---

## Remaining risks

| Risk | Mitigation |
|------|------------|
| Render disk not mounted / wrong `KYC_DATA` | Upload blocked at `require_intake_upload_allowed()`; production 503 |
| Operator auth unavailable during incident | Public upload still fails closed; health/ready expose storage flags |
| Incident log growth | JSONL under `intakes/integrity_incidents.jsonl`; operator integrity endpoints |
| Quarantine mirror disk usage | Mirror only on successful proof gate; same files as canonical |

---

## Key files

- `services/intake/proof_gate.py` — proof gate + live boot status
- `services/intake/quarantine.py` — quarantine mirror
- `services/intake/delete_protection.py` — delete protection
- `services/intake/intake.py` — wired into `process_upload`
- `server.py` — live endpoints
- `tests/test_upload_immutability.py` — destructive matrix
