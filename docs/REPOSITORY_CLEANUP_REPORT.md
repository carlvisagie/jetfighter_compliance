# Repository Cleanup Report

**Cleanup Date:** 2026-06-12  
**Patch:** PRE-LAUNCH-2  
**Source:** REPOSITORY_TRUTH_AUDIT.md

---

## Summary

| Action | Count |
|--------|-------|
| Items archived | 21 |
| Items moved | 6 |
| Legacy scripts marked | 3 |
| Items deleted | 5 |

---

## PHASE 1 — Items Archived

### TXT Note Files → `archive/root_cleanup/`

| File | Status |
|------|--------|
| `A) Autostart the tunnel (uses your.txt` | ✅ Archived |
| `go to the right folder (PS5-safe).txt` | ✅ Archived |
| `One-liner to open the Control Panel.txt` | ✅ Archived |

### Pilot Artifacts → `archive/pilot_artifacts/`

| File | Status |
|------|--------|
| `pilot_baseline_metrics.json` | ✅ Archived |
| `pilot_known_limitations.json` | ✅ Archived |
| `pilot_readiness_checklist.json` | ✅ Archived |
| `pilot_release_report.json` | ✅ Archived |

### Audit Reports → `archive/root_cleanup/`

| File | Status |
|------|--------|
| `adversarial_audit_report.json` | ✅ Archived |
| `corpus_results.json` | ✅ Archived |
| `decision_quality_report.json` | ✅ Archived |
| `overall_corpus_score.json` | ✅ Archived |
| `reserved_words_report.json` | ✅ Archived |

### Legacy Utility Scripts → `archive/root_cleanup/`

| File | Status |
|------|--------|
| `dns_reset_and_audit.ps1` | ✅ Archived |
| `stage1_install.ps1` | ✅ Archived |
| `sync_to_extreme_nightly.ps1` | ✅ Archived |
| `JetFighter_Launch_Compliance.bat` | ✅ Archived |

### Validation Data → `archive/root_cleanup/`

| File | Status |
|------|--------|
| `validation-e2e-production.csv` | ✅ Archived |

### VIO Brief → `archive/.vio_brief/`

| Directory | Status |
|-----------|--------|
| `.vio_brief/` (34 files) | ✅ Archived |

---

## PHASE 2 — Items Moved

| Item | From | To | Status |
|------|------|-----|--------|
| `audit_companies.py` | Root | `archive/dev_tools/` | ✅ Moved |
| `generate_qr.py` | Root | `scripts/` | ✅ Moved |
| `pilot_restore_point.md` | Root | `docs/` | ✅ Moved |
| `ORGANISM_CONSTITUTION_AUDIT.md` | Root | `docs/` | ✅ Moved |
| `.vio_brief/` | Root | `archive/` | ✅ Moved |
| `drafts/telemetry_fastapi_endpoint.py` | `drafts/` | `archive/dev_tools/` | ✅ Moved |

---

## PHASE 3 — Legacy Startup Scripts

All three scripts marked with LEGACY banner pointing to `start_production.ps1`:

| Script | Status | Banner Added |
|--------|--------|--------------|
| `start_everything.ps1` | LEGACY | ✅ Yes |
| `start_live_platform.ps1` | LEGACY | ✅ Yes |
| `fix_everything.ps1` | LEGACY | ✅ Yes |

**Canonical startup path:** `start_production.ps1`

---

## PHASE 4 — Reference Findings

### References to Legacy Startup Scripts

| Document | Reference | Action Needed |
|----------|-----------|---------------|
| `docs/README.md` | "start_everything.ps1 ... are not deploy or runtime truth" | NO — Correctly marked as NOT production |
| `docs/PRODUCTION_ENGINEERING_DOCTRINE.md` | "Local PowerShell is never production" | NO — Correctly marked as NOT production |
| `docs/REPOSITORY_TRUTH_AUDIT.md` | Audit document lists scripts | NO — Informational only |
| `archive/legacy/stripe/*` | Historical docs | NO — Already archived |

**Conclusion:** No documentation changes needed. All references correctly identify these as non-production scripts.

---

## PHASE 5 — Organism Directory Investigation

### Status: LEGACY — DO NOT DELETE

**Location:** `organism/`

**Contents:**
- `database.py` — SQLite database connection (`sqlite:///./organism/data/kyc.db`)
- `models.py` — SQLAlchemy models (imports from `organism.database`)
- `services/event_log.py` — Event logging service
- `tests/test_smoke.py` — Smoke test
- `docs/TEST_DOCTRINE.md` — Test documentation

**Referenced By:**

| Location | Reference Type |
|----------|---------------|
| `organism/models.py` | Imports `organism.database` |
| `organism/services/event_log.py` | Imports `organism.database`, `organism.models` |
| `organism/tests/test_smoke.py` | Imports `organism.database`, `organism.services.event_log` |
| `services/memory/organism_integration.py` | Documents as "bridged island" |

**Documentation Status:**

From `services/memory/organism_integration.py`:
```python
{
    "label": "organism/ sqlite subsystem",
    "paths": ["organism/"],
    "is_bridged": True,
    "reads": ["organism/data/kyc.db"],
    "writes": ["organism/data/kyc.db"],
}
```

**Conclusion:**
- **HISTORICAL/LEGACY** — Not production truth
- **Properly documented** as "bridged island" outside production truth
- **Has active internal imports** — Cannot be deleted without code changes
- **Recommendation:** Leave as-is; already documented as legacy

---

## Items Deleted

| File | Reason |
|------|--------|
| `New Text Document.txt` | Empty file |
| `SOSWY_AnnualReport.pdf` | Business document (should not be in repo) |
| `SOSWY_RECEIPT.pdf` | Business document (should not be in repo) |
| `SOSWY_RECEIPT (1).pdf` | Business document (should not be in repo) |
| `SOSWY_Reinstatement.pdf` | Business document (should not be in repo) |

---

## New Archive Structure

```
archive/
├── .vio_brief/                    # VIO cursor brief package (34 files)
├── dev_tools/                     # Development/debug scripts
│   ├── audit_companies.py
│   ├── telemetry_fastapi_endpoint.py
│   └── ... (45+ existing scripts)
├── legacy/
│   └── stripe/                    # Banned Stripe integration
├── pilot_artifacts/               # NEW — Pilot phase artifacts
│   ├── pilot_baseline_metrics.json
│   ├── pilot_known_limitations.json
│   ├── pilot_readiness_checklist.json
│   └── pilot_release_report.json
└── root_cleanup/                  # NEW — Root clutter cleanup
    ├── A) Autostart the tunnel (uses your.txt
    ├── JetFighter_Launch_Compliance.bat
    ├── One-liner to open the Control Panel.txt
    ├── adversarial_audit_report.json
    ├── corpus_results.json
    ├── decision_quality_report.json
    ├── dns_reset_and_audit.ps1
    ├── go to the right folder (PS5-safe).txt
    ├── overall_corpus_score.json
    ├── reserved_words_report.json
    ├── stage1_install.ps1
    ├── sync_to_extreme_nightly.ps1
    └── validation-e2e-production.csv
```

---

## Verification

| Check | Status |
|-------|--------|
| No production behavior changes | ✅ |
| No deployment behavior changes | ✅ |
| No acquisition behavior changes | ✅ |
| No deletions of tracked code | ✅ |
| History preserved via git mv | ✅ |

---

## Root Directory (After Cleanup)

**Remaining root items:**

| Category | Items |
|----------|-------|
| Production files | `AGENTS.md`, `Dockerfile`, `render.yaml`, `requirements.txt`, `server.py`, `pytest.ini` |
| Config files | `.gitignore`, `.env` (gitignored), `.ops_env` (gitignored) |
| Startup scripts | `start_production.ps1` (canonical), `open_control_panel.ps1`, `run_tunnel.ps1`, `setup_run.ps1` |
| Legacy scripts | `start_everything.ps1`, `start_live_platform.ps1`, `fix_everything.ps1` (marked LEGACY) |
| Directories | `archive/`, `data/`, `docs/`, `organism/`, `organism_core/`, `schemas/`, `scripts/`, `services/`, `tests/`, `tests_archived/`, `ui/`, `vio-frontend/` |

**Items removed from root:** 26 files
