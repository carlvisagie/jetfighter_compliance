# Restore Point — Production Baseline

**Recorded:** 2026-06-07 (Patch 11 — Production Fortress)  
**Purpose:** Known-good production baseline for recovery and forensic comparison.

---

## Current production commit

| Field | Value |
|-------|-------|
| SHA (short) | `c7fcbc9` |
| SHA (full) | `c7fcbc9132131657c7c1bb1f6d52c65b8f417f84` |
| Branch | `main` |
| Message | fix: repair stale intake expected counts from durable disk truth (Patch 10C) |

Verify live: `GET https://compliance.keepyourcontracts.com/api/public/build-info`

## Current Render service

| Field | Value |
|-------|-------|
| Name | `jetfighter_compliance` |
| ID | `srv-d83gut57vvec739efv6g` |
| URL | `https://jetfighter-compliance.onrender.com` |
| Custom domain | `compliance.keepyourcontracts.com` |
| Disk | `kyc-data` @ `/var/data` (10 GB) |

## Current data root

```
/var/data/
├── intakes/<FB-*>/uploads/     # canonical customer files
├── projects/<FB-*>/             # evidence + EI artifacts
└── data/memory/                 # organism memory (under active root)
```

**Disk is the recovery source of truth** — redeploying code does not replace disk content if mount persists.

## Deployment date

- **2026-06-07** — Patch 10C deployed (`c7fcbc9`), intake integrity repair verified on 4 production intakes.
- **2026-06-04** — Disk attach incident resolved; persistent mount confirmed.

## Test baseline at restore point

- **1051** pytest tests, all passing (Patch 11 validation).

## Recovery procedure

### 1. Service unhealthy after deploy

1. Check Render logs for boot / disk / env errors.
2. Confirm `KYC_DATA=/var/data` and disk attached in dashboard.
3. Roll back deploy to this SHA (`c7fcbc9`) via Render **Rollback** if new commit is suspect.
4. Verify: `/healthz`, `/api/public/build-info`, `/api/operator/intake/reconcile`.

### 2. Data visible in dashboard but not in app

1. SSH / disk browser: confirm files under `/var/data/intakes/`.
2. Run `GET /api/operator/intake/reconcile/{id}` per intake.
3. If metadata stale only: `POST /api/operator/integrity/repair/{id}` (never deletes files).
4. If disk empty after deploy: **SEV-1** — disk mount regression; stop uploads; see [`KYC_UPLOAD_IMMUTABILITY_PROOF.md`](KYC_UPLOAD_IMMUTABILITY_PROOF.md).

### 3. Full platform restore

1. Redeploy commit `c7fcbc9` (or newer verified gate-passing commit).
2. Ensure disk snapshot restore from Render if hardware failure (disk snapshot feature).
3. Re-run [`DEPLOYMENT_GATE.md`](DEPLOYMENT_GATE.md) post-deploy checks.
4. Update this document with new SHA if baseline moves forward intentionally.

---

*Previous restore points should be appended below with date + SHA — do not delete history.*

| Date | SHA | Notes |
|------|-----|-------|
| 2026-06-07 | `c7fcbc9` | Patch 10C integrity repair + Patch 11 fortress docs |
