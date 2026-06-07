# Production Truth Audit

**Last updated:** 2026-06-07 (Patch 11 — Production Fortress)  
**Doctrine:** [`PRODUCTION_IS_THE_ONLY_TRUTH.md`](PRODUCTION_IS_THE_ONLY_TRUTH.md)  
**Governance:** [`PRODUCTION_CONSTITUTION.md`](PRODUCTION_CONSTITUTION.md)

This document is the **live production snapshot**. Capability inventory (feature-level GREEN/AMBER) remains in [`DEPLOYMENT_INVENTORY.md`](DEPLOYMENT_INVENTORY.md) — update that file only for capability status, not for commit/test counts.

---

## Canonical Repository

| Field | Value |
|-------|-------|
| Git remote | `https://github.com/carlvisagie/jetfighter_compliance.git` |
| Local path | `E:/JetFighter_Compliance` (developer machines — **not** data truth) |

## Canonical Branch

`main` — protected per [`GITHUB_PROTECTION.md`](GITHUB_PROTECTION.md).

## Canonical Production URL

| URL | Role |
|-----|------|
| `https://compliance.keepyourcontracts.com` | Branded customer + operator host |
| `https://jetfighter-compliance.onrender.com` | Render fallback (must match commit) |

## Canonical Render Service

| Field | Value |
|-------|-------|
| Dashboard name | `jetfighter_compliance` |
| Service ID | `srv-d83gut57vvec739efv6g` |
| Plan | `starter` (Docker) |
| Health | `GET /healthz` |
| Disk | `kyc-data` → `/var/data` (10 GB, attached 2026-06-04) |
| Blueprint note | `render.yaml` lists `kyc-backend` — **live service name differs**; do not reapply blueprint without migration plan |

## Canonical Data Root

| Environment | Path | Trust |
|-------------|------|-------|
| Production | `/var/data` (`KYC_DATA`) | **trusted** |
| Local / pytest | temp dirs only | **DO_NOT_TRUST** |

Customer intakes: `/var/data/intakes/<FB-*>/`  
Organism memory: `/var/data/data/memory/` (under active data root layout)  
Projects/EI: `/var/data/projects/<FB-*>/`

## Canonical Intake Flow

`POST /api/intake/upload` → durability → hash verify → audit → index → proof gate → queue.  
Reconcile: `GET /api/operator/intake/reconcile`.  
See [`architecture/intake.md`](architecture/intake.md).

## Canonical Evidence Flow

Intake uploads → optional `projects/<id>/evidence/` mirror → EI under `projects/<id>/evidence_intelligence/`.  
Registry derived from disk + audit + transactions.  
Organism check: `evidence_vs_files`.

## Canonical Organism Flow

`GET /api/operator/organism/state` — collectors → checks → snapshot.  
Eight KYC checks including `disk_vs_intake_index`, `evidence_vs_files`.

## Canonical VIO Flow

`/ui/vio.html` ← `GET /api/operator/vio/overview` + cognitive topology.  
Environment ribbon required on operator surfaces.

## Current Test Count

| Metric | Value |
|--------|-------|
| Suite | `python -m pytest tests/ -q` |
| Count | **1051** tests (Patch 11 validation) |
| Pass | **1051** / 1051 |
| CI | `.github/workflows/kyc_guardrails.yml` |

## Current Production Commit

| Field | Value |
|-------|-------|
| SHA (short) | `c7fcbc9` |
| SHA (full) | `c7fcbc9132131657c7c1bb1f6d52c65b8f417f84` |
| Message | Patch 10C — intake integrity mismatch repair |
| Verified on branded URL | 2026-06-07 |

Re-verify: `GET /api/public/build-info` on both production URLs.

## Known Risks

| Risk | Mitigation |
|------|------------|
| Blueprint vs live service name mismatch | Manage disk via dashboard/API; see `render.yaml` header |
| `integrity_proof` fleet `ok: false` with unsigned audit receipts | Track separately; does not block intake reconcile |
| Concurrent multi-upload races | Sequential batches preferred; integrity repair endpoint |
| Local `data/` pollution | Never cite local counts; `_env.trust` envelope |
| Reserved-word drift in active code | `scripts/audit_reserved_words.py` |

## Known Limitations

- `organism/` SQLAlchemy tree excluded from CI — not runtime truth (`organism_core/` is canonical).
- Shopify / legacy card-payment rails inactive or banned.
- OCR quality depends on scan resolution; unsupported types stay `pending_analysis`.
- Acquisition connectors require live API credentials; manual mode default.

---

*Next audit trigger: any production deploy, SEV-1 incident, or patch labeled “fortress” / “truth”.*
