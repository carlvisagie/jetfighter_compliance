# Deployment Gate Checklist

**Use before any production deploy.**  
**No deploy changes in fortress-only patches** unless owner explicitly authorizes.

Companion: [`PRODUCTION_CONSTITUTION.md`](PRODUCTION_CONSTITUTION.md) §10–11.

---

## Pre-merge (repository)

- [ ] `python -m pytest tests/ -q` — full suite green (record count in commit / RESTORE_POINT)
- [ ] `pytest tests/test_public_ui_exposure.py tests/test_ops_route_auth.py tests/test_kyc_guardrails.py -q`
- [ ] `python scripts/audit_reserved_words.py` — no violations in active tree
- [ ] No secrets in diff (`.env`, `.ops_env`, tokens)
- [ ] [`PRODUCTION_TRUTH_AUDIT.md`](PRODUCTION_TRUTH_AUDIT.md) updated if production facts changed

## Pre-deploy (target: Render `jetfighter_compliance`)

- [ ] Confirm disk `kyc-data` still mounted at `/var/data` on live service
- [ ] `ENVIRONMENT=production`, `KYC_DATA=/var/data` unchanged
- [ ] Intended commit SHA recorded in [`RESTORE_POINT.md`](RESTORE_POINT.md)

## Post-deploy (production HTTP)

Run with `.ops_env` (`OPS_PASSWORD`) via `scripts/lib/ops_client.py`:

| Check | Command / endpoint | Pass criterion |
|-------|-------------------|----------------|
| Health | `GET /healthz` | 200 |
| Readiness | `GET /health/ready` | 200 |
| Build info | `GET /api/public/build-info` | `git_commit` matches deploy SHA on **both** branded + Render URLs |
| VIO | `python scripts/probe_vio_overview.py` | Overview JSON valid shape |
| Evidence reconciliation | `GET /api/operator/organism/state` | `evidence_vs_files.ok == true` |
| Intake fleet | `GET /api/operator/intake/reconcile` | `failing_intake_ids` empty |
| Scheduler heartbeat | `python scripts/probe_boot_status.py` | Scheduler started, cron jobs registered |

Optional deeper proofs:

- `python scripts/prove_disk_persistence.py`
- `python scripts/repair_intake_integrity_patch10c.py` (after integrity patches only)

## Post-deploy documentation

- [ ] Update [`PRODUCTION_TRUTH_AUDIT.md`](PRODUCTION_TRUTH_AUDIT.md) — commit SHA, date, test count
- [ ] Update [`RESTORE_POINT.md`](RESTORE_POINT.md) if this deploy is a new baseline

---

**Gate owner:** Platform operator.  
**Automated CI gate:** GitHub Actions `kyc_guardrails.yml` on PR to `main`.
