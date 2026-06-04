# KYC Upload Immutability Proof

**Date:** 2026-05-30 (initial) · **Last reviewed:** 2026-06-04
**Repo:** [carlvisagie/jetfighter_compliance](https://github.com/carlvisagie/jetfighter_compliance)
**Production:** https://compliance.keepyourcontracts.com (Render service `jetfighter_compliance`)

---

## Canonical statement

**A successful upload cannot disappear without a SEV-1 forensic incident.**

Customer-visible success (`customer_may_show_success=true`, `proof_gate_passed=true`) is returned only after a synchronous proof gate verifies the intake is immediately discoverable on durable disk, in the index, operator queue/archive, retention-check, file list, and download/view paths.

---

## 2026-06-04 — Disk attach incident (SEV-1, closed)

**Symptom.** Production reported `intakes=0, uploads=0` in the organism overview
despite Carl having uploaded paperwork for five test companies through the
customer portal. Earlier forensic snapshots had recorded 40 intakes and 40
uploads on disk.

**Root cause.** The live Render service `jetfighter_compliance` ran with
`KYC_DATA=/var/data` but **no persistent disk attached to that mount path**.
Each redeploy/restart created a fresh container-local `/var/data`, and every
upload from the previous boot was erased. The upload code itself was correct;
the storage substrate underneath it was ephemeral.

**Why the proof gate did not catch it.** The proof gate verifies post-write
visibility *within the running process*. It cannot, on its own, see whether
the underlying filesystem will survive the next container restart — that is a
question only a cross-restart probe can answer.

**Fix (deployed 2026-06-04T08:14:43Z).**

1. A 10 GB Render persistent disk named `kyc-data` was attached at `/var/data`
   on `jetfighter_compliance` and recorded in `render.yaml` (`disk.mountPath:
   /var/data`, `disk.sizeGB: 10`).
2. A new disk-persistence observability layer was added so this regression is
   detected automatically on every boot:
   - `services/durable_storage.py` writes a one-time marker
     (`<KYC_DATA>/.disk_marker`) on first boot containing `marker_birth_utc`.
   - `services/organism_state/collectors.py::DiskPersistenceCollector` reads
     that marker on every boot.
   - `services/organism_state/checks.py::DiskPersistenceCheck` compares the
     marker's birth timestamp to the current process start; if the marker
     disappears or its birth timestamp resets across a restart, the organism
     flips to **RED `ephemeral_lost`** (auto SEV-1) and refuses to claim it is
     production-ready.
   - States: `pending_first_restart` (AMBER, just deployed), `verified_persistent`
     (INFO, marker survived ≥ one restart), `ephemeral_lost` (RED, marker
     missing — SEV-1 ephemeral regression), `write_failed` (RED, write path
     itself broken).

**Live verification (2026-06-04).**

| Probe | Boot | Result |
|-------|------|--------|
| `scripts/prove_disk_persistence.py` (explicit restart) | pre + post | `verified_persistent`, `marker_birth_utc` unchanged |
| Full code redeploy | pre + post | `verified_persistent`, `marker_birth_utc` unchanged |

**Operator runbook:**

```powershell
python -m scripts.probe_boot_status     # scheduler + organism status
python -m scripts.prove_disk_persistence # cross-restart marker proof
```

If either probe reports `ephemeral_lost`, `write_failed`, or a changed
`marker_birth_utc` across a restart, **the disk mount is gone** — open the
Render service `jetfighter_compliance` → Disks tab, re-attach `kyc-data` at
`/var/data`, and re-run the probe. Do not accept new customer uploads until
the probe is green.

**Status:** Closed. Disk attached. Marker verified persistent across two
independent boot events. Detection wired into the organism so this class of
regression cannot recur silently.

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
3. Upload 13 PDFs via `/ui/intake` or `POST /api/intake/upload`
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
- `services/intake/inventory.py` — single inventory truth + agreement verifier
- `tests/test_inventory_agreement.py` — cross-endpoint count agreement
- `scripts/verify_production_inventory.py` — production inventory checker

---

## Inventory agreement fix (2026-05-30, commit `2b66fd3`)

### Root cause of diagnostics disagreement

| Source | What it reported | Why |
|--------|------------------|-----|
| `retention_scan.intake_directories` | `0` | **Cached boot snapshot** (`last_startup_retention_scan()`) from container start when disk was empty |
| `intake_directories_found` | `1` | **Live** `list_intake_ids()` at request time |
| `queue_depth` | `2` | Live queue from pending-review intakes on disk |
| `live_scan_status` | `degraded` | Stale boot counts + amber/incident heuristics even when live disk and queue agreed |

### Fix

One module — `build_intake_inventory()` — feeds every operator-facing count. `retention_scan` is now live (`scan_type: live`). Boot snapshot moved to `startup_retention_snapshot` (audit only). `verify_inventory_agreement()` fails if any endpoint disagrees.

### Tests added (`tests/test_inventory_agreement.py`)

| Test | Purpose |
|------|---------|
| `test_inventory_agreement_after_single_upload` | All endpoints match after 1-file upload |
| `test_inventory_agreement_thirteen_files` | 13-file batch agreement |
| `test_retention_scan_not_stale_startup_snapshot` | `retention_scan` is live, not boot cache |
| `test_no_degraded_when_proof_gate_passed` | `live_scan_status=healthy` when gate passes |
| `test_queue_depth_equals_pending_review` | Queue depth = `pending_review_count` |

**Local run:** 5 passed; full `tests/` suite: 710 passed (1 unrelated cognitive_topology flake).

### Production verification

```powershell
$env:OPS_PASSWORD = "<Render dashboard OPS_PASSWORD>"
python scripts/verify_production_inventory.py
```

After deploy of `2b66fd3`, expect `"ok": true`, `"live_scan_status": "healthy"`, identical `intake_directories` and `upload_files` across inventory, retention_scan, diagnostics, raw-disk-scan, and live boot.

**Automated run from agent (2026-05-30):** `401 ops_auth_failed` — local `OPS_PASSWORD` does not match production. Carl must run the script after deploy with dashboard credentials.
