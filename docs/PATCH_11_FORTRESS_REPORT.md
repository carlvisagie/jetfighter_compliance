# Patch 11 — Production Fortress Report

**Date:** 2026-06-07  
**Type:** Governance, documentation, hardening, cleanup — **no feature or business-logic changes**  
**Deploy:** None (per patch scope — documentation + repository sanitization only)

---

## Summary

Established production governance layer: constitution, architecture index, truth audit, deployment gate, restore point, agent protected-systems rules, reserved-word scanner, and dev-tool archival. Consolidated with existing canonical docs (`KYC_CONSTITUTION`, `PRODUCTION_IS_THE_ONLY_TRUTH`, `DEPLOYMENT_INVENTORY`) instead of duplicating them.

---

## Files created

| File | Purpose |
|------|---------|
| `docs/PRODUCTION_CONSTITUTION.md` | Production governance — architecture, flows, forbidden changes |
| `docs/PRODUCTION_TRUTH_AUDIT.md` | Live production snapshot (commit, tests, risks) |
| `docs/architecture/organism.md` | Subsystem architecture card |
| `docs/architecture/evidence_intelligence.md` | Subsystem architecture card |
| `docs/architecture/memory.md` | Subsystem architecture card |
| `docs/architecture/acquisition.md` | Subsystem architecture card |
| `docs/architecture/vio.md` | Subsystem architecture card |
| `docs/architecture/intake.md` | Subsystem architecture card |
| `docs/ARCHIVED_FILES.md` | Archive inventory |
| `docs/GITHUB_PROTECTION.md` | Target `main` branch protection rules |
| `docs/DEPLOYMENT_GATE.md` | Pre/post deploy checklist |
| `docs/RESTORE_POINT.md` | Production baseline `c7fcbc9` |
| `docs/history/README.md` | Historical docs policy |
| `docs/PATCH_11_FORTRESS_REPORT.md` | This report |
| `scripts/audit_reserved_words.py` | Reserved-word governance scanner |
| `reserved_words_report.json` | Scanner output (0 findings on active source) |

## Files archived (50 → `archive/dev_tools/`)

Root one-offs: `.check*` (8), `.probe*` (4), `run_audit*` (4), `run_*corpus*` / OCR (3), `.git_commit_msg*` (6), polls/probes/live JS snapshots (25). Full list: [`ARCHIVED_FILES.md`](ARCHIVED_FILES.md).

## Files moved (not deleted)

| From | To |
|------|-----|
| `docs/VIO_SOURCE_BRIEF.md` | `docs/history/VIO_SOURCE_BRIEF.md` |

## Files modified

| File | Change |
|------|--------|
| `AGENTS.md` | PROTECTED SYSTEMS section; truth-audit read order; test count |
| `docs/KYC_CONSTITUTION.md` | Cross-link to production constitution |
| `docs/DEPLOYMENT_INVENTORY.md` | Delegates live counts to truth audit |
| `docs/VIO_CONSTITUTION.md` | Links → `docs/history/VIO_SOURCE_BRIEF.md` |
| `docs/VIO_ABSORPTION_INVENTORY.md` | Brief path update |

**Not modified:** `server.py`, intake, EI, memory, acquisition, VIO runtime code, `render.yaml`, UI.

---

## Validation

| Check | Result |
|-------|--------|
| `python -m pytest tests/ -q` | **1051 passed** / 1051 |
| `python scripts/audit_reserved_words.py` | **ok: true** (0 findings on active source) |
| Production deploy | **Skipped** (patch scope) |

---

## Remaining risks

| Risk | Notes |
|------|-------|
| GitHub branch protection | Documented in `GITHUB_PROTECTION.md` — confirm enabled in repo settings |
| Production commit unchanged | Still `c7fcbc9` until next authorized deploy |
| Local `data/` dev fixtures | Excluded from reserved-word scan; not production truth |
| `integrity_proof` unsigned receipts | Pre-existing fleet item; tracked in truth audit |
| Blueprint vs live Render service name | Documented in constitution + `render.yaml` header |

---

## Canonical pointers (one truth)

| Topic | Document |
|-------|----------|
| Environment law | `PRODUCTION_IS_THE_ONLY_TRUTH.md` |
| Organism law | `KYC_CONSTITUTION.md` |
| Production governance | `PRODUCTION_CONSTITUTION.md` |
| Live snapshot | `PRODUCTION_TRUTH_AUDIT.md` |
| Deploy gate | `DEPLOYMENT_GATE.md` |
| Recovery | `RESTORE_POINT.md` |
| Subsystem cards | `docs/architecture/*.md` |

---

*Patch 11 complete. Repository simplified: fewer root clutter files, clearer doc ownership, no duplicate constitution.*
