# Repository Truth Audit

**Audit Date:** 2026-06-12  
**Source of Truth:** Production (SHA `6ef13df`)

---

## PHASE 1 — ROOT INVENTORY

### Directories

| Directory | Classification | Purpose | Status |
|-----------|---------------|---------|--------|
| `.cloudflared/` | DEVELOPMENT | Cloudflare tunnel config (gitignored) | Local dev only |
| `.git/` | DEVELOPMENT | Git repository | Standard |
| `.github/` | PRODUCTION | CI workflows (`kyc_guardrails.yml`) | Active |
| `.pytest_cache/` | DEVELOPMENT | Pytest cache (gitignored) | Ephemeral |
| `.venv/` | DEVELOPMENT | Python venv (gitignored) | Local dev only |
| `.vio_brief/` | ARCHIVE | VIO cursor brief package | Historical |
| `archive/` | ARCHIVE | Legacy systems (Stripe, dev tools) | Historical |
| `bin/` | DEVELOPMENT | Cloudflare binary (gitignored) | Local dev only |
| `data/` | PRODUCTION | Production data (partially gitignored) | Active |
| `docs/` | PRODUCTION | Documentation | Active |
| `drafts/` | DEVELOPMENT | Draft code/designs | Unused |
| `organism/` | LEGACY | Old organism sqlite (not production truth) | Legacy |
| `organism_core/` | PRODUCTION | Organism adapter | Active |
| `schemas/` | PRODUCTION | JSON schemas | Active |
| `scripts/` | OPERATOR | Production/dev scripts | Mixed |
| `services/` | PRODUCTION | Core business logic | Active |
| `tests/` | PRODUCTION | Test suite | Active |
| `tests_archived/` | ARCHIVE | Archived VIO tests | Historical |
| `ui/` | PRODUCTION | HTML/JS UI | Active |
| `vio-frontend/` | DEVELOPMENT | VIO React source (node_modules gitignored) | Development |
| `__pycache__/` | DEVELOPMENT | Python cache | Ephemeral |

### Root Files

| File | Classification | Purpose | Status |
|------|---------------|---------|--------|
| `AGENTS.md` | PRODUCTION | Agent rules (binding) | Active |
| `Dockerfile` | PRODUCTION | Container build | Active |
| `pytest.ini` | PRODUCTION | Test configuration | Active |
| `render.yaml` | PRODUCTION | Render deployment spec | Active |
| `requirements.txt` | PRODUCTION | Python dependencies | Active |
| `server.py` | PRODUCTION | FastAPI application | Active |
| `.env` | DEVELOPMENT | Local env (gitignored) | Local only |
| `.ops_env` | OPERATOR | Ops credentials (gitignored) | Operator only |
| `.gitignore` | PRODUCTION | Git exclusions | Active |

---

## PHASE 2 — STARTUP PATH AUDIT

### Startup Scripts

| Script | Purpose | Owner | Classification | Status |
|--------|---------|-------|----------------|--------|
| `start_everything.ps1` | Local dev: uvicorn + tunnel + open control | Developer | DEVELOPMENT | **LEGACY** — refers to port 8000, kyc-prod tunnel |
| `start_live_platform.ps1` | Local dev: uvicorn + tunnel + open shop/intake | Developer | DEVELOPMENT | **LEGACY** — duplicates start_production |
| `start_production.ps1` | Local dev: uvicorn + tunnel + health check | Developer | DEVELOPMENT | **ACTIVE** — best local dev script |
| `run_tunnel.ps1` | Start Cloudflare tunnel only | Developer | DEVELOPMENT | **ACTIVE** — utility |
| `setup_run.ps1` | Initial venv/pip setup | Developer | DEVELOPMENT | **ACTIVE** — one-time setup |
| `fix_everything.ps1` | Kill processes + restart + open control | Developer | DEVELOPMENT | **LEGACY** — duplicates others |
| `open_control_panel.ps1` | Start server if needed + open control | Developer | DEVELOPMENT | **ACTIVE** — operator convenience |

### Analysis

| Issue | Scripts Affected |
|-------|-----------------|
| **Duplicate functionality** | `start_everything.ps1`, `start_live_platform.ps1`, `start_production.ps1`, `fix_everything.ps1` all do similar things |
| **Inconsistent ports** | `start_everything.ps1` uses 8000, others use 8080 |
| **Inconsistent tunnel names** | `kyc-prod`, `jetfighter-compliance`, config-jetfighter.yml, config-kyc.yml |

---

## PHASE 3 — DUPLICATE PATH AUDIT

### Duplicate Startup Paths

| Function | Scripts |
|----------|---------|
| Start uvicorn + tunnel | `start_everything.ps1`, `start_live_platform.ps1`, `start_production.ps1`, `fix_everything.ps1` |
| Open control panel | `start_everything.ps1`, `fix_everything.ps1`, `open_control_panel.ps1` |
| Kill old processes | All four main scripts |

**Recommendation:** Consolidate to `start_production.ps1` (best health check) + `open_control_panel.ps1` (utility).

### Duplicate Verification Paths

| Function | Scripts |
|----------|---------|
| Verify Render production | `scripts/verify-render-production.ps1` |
| Verify production live | `scripts/verify-production-live.ps1` |
| Verify uptime stability | `scripts/verify-uptime-stability.ps1` |
| Verify founding pilot | `scripts/verify_founding_pilot_pipeline.ps1` |

**Status:** All four serve distinct purposes — no duplicates.

### Duplicate Launch Paths

| Documented Launch Path | Status |
|------------------------|--------|
| `docs/LAUNCH_PATH.md` | **CANONICAL** |
| `docs/README.md` | References LAUNCH_PATH |
| `docs/PRODUCTION_CONSTITUTION.md` | Governance only |

**Status:** Single canonical path — no conflicts.

---

## PHASE 4 — ARCHIVE AUDIT

### `archive/` Structure

| Path | Contents | Status |
|------|----------|--------|
| `archive/legacy/stripe/` | Banned Stripe integration docs/code | HISTORICAL |
| `archive/legacy/stripe/docs/` | 25+ historical Stripe-era documents | HISTORICAL |
| `archive/legacy/stripe/drafts/` | Draft telemetry/lead plans | HISTORICAL |
| `archive/legacy/stripe/html/` | Old HTML files | HISTORICAL |
| `archive/dev_tools/` | 45+ temporary dev/debug scripts | HISTORICAL |

**Status:** Properly archived. No action needed.

### `tests_archived/` Structure

| Path | Contents | Status |
|------|----------|--------|
| `tests_archived/legacy_vio_ui/` | 11 archived VIO UI tests | HISTORICAL |

**Status:** Properly archived. Tests were superseded by current VIO implementation.

### `.vio_brief/` Structure

| Path | Contents | Status |
|------|----------|--------|
| `.vio_brief/VIO_Cursor_Brief_Package/` | VIO cursor brief markdown | HISTORICAL |

**Status:** Historical reference. Could be moved to `archive/`.

---

## PHASE 5 — ROOT CLUTTER AUDIT

### TXT Files (Root)

| File | Purpose | Classification | Recommendation |
|------|---------|----------------|----------------|
| `A) Autostart the tunnel (uses your.txt` | Old operator guide with tunnel setup | LEGACY | ARCHIVE |
| `export latest project's binder (avoid $pid).txt` | One-liner note | LEGACY | ARCHIVE |
| `go to the right folder (PS5-safe).txt` | One-liner note | LEGACY | ARCHIVE |
| `One-liner to open the Control Panel.txt` | One-liner note | LEGACY | ARCHIVE |
| `New Text Document.txt` | Empty file | CLUTTER | DELETE |

### PDF Files (Root — currently deleted/unstaged)

| File | Status |
|------|--------|
| `SOSWY_AnnualReport.pdf` | Deleted (unstaged) |
| `SOSWY_RECEIPT.pdf` | Deleted (unstaged) |
| `SOSWY_RECEIPT (1).pdf` | Deleted (unstaged) |
| `SOSWY_Reinstatement.pdf` | Deleted (unstaged) |

**Status:** PDFs were deleted but not committed. Business documents should not be in repo.

### JSON Files (Root)

| File | Purpose | Classification | Recommendation |
|------|---------|----------------|----------------|
| `adversarial_audit_report.json` | Audit output | TEMPORARY | ARCHIVE |
| `corpus_results.json` | Corpus test output | TEMPORARY | ARCHIVE |
| `decision_quality_report.json` | Audit output | TEMPORARY | ARCHIVE |
| `overall_corpus_score.json` | Corpus test output | TEMPORARY | ARCHIVE |
| `pilot_baseline_metrics.json` | Pilot metrics | TEMPORARY | ARCHIVE |
| `pilot_known_limitations.json` | Pilot notes | TEMPORARY | ARCHIVE |
| `pilot_readiness_checklist.json` | Pilot checklist | TEMPORARY | ARCHIVE |
| `pilot_release_report.json` | Pilot report | TEMPORARY | ARCHIVE |
| `reserved_words_report.json` | Audit output | TEMPORARY | ARCHIVE |

### Log Files (Root)

| File | Purpose | Classification | Recommendation |
|------|---------|----------------|----------------|
| `.pt.log` | Pytest log | TEMPORARY | GITIGNORED |
| `.pytest-full.log` | Pytest log | TEMPORARY | GITIGNORED |
| `.pytest-full2.log` | Pytest log | TEMPORARY | GITIGNORED |
| `.pytest-vio-fix.log` | Pytest log | TEMPORARY | GITIGNORED |
| `.pytest_full.log` | Pytest log | TEMPORARY | GITIGNORED |
| `audit-pytest.log` | Audit log | TEMPORARY | GITIGNORED |
| `install_stage1.log` | Install log | TEMPORARY | GITIGNORED |
| `validation-e2e-production.log` | Validation log | TEMPORARY | GITIGNORED |
| `validation-pytest.log` | Validation log | TEMPORARY | GITIGNORED |
| `validation-verify-live.log` | Validation log | TEMPORARY | GITIGNORED |
| `validation-verify-render.log` | Validation log | TEMPORARY | GITIGNORED |

**Note:** `.gitignore` has `*.log` — these should not be tracked.

### Other Root Files

| File | Purpose | Classification | Recommendation |
|------|---------|----------------|----------------|
| `audit_companies.py` | One-off audit script | TEMPORARY | MOVE to scripts/ or archive/ |
| `generate_qr.py` | QR generation | TEMPORARY | MOVE to scripts/ |
| `dns_reset_and_audit.ps1` | DNS utility | LEGACY | ARCHIVE |
| `stage1_install.ps1` | Old install script | LEGACY | ARCHIVE |
| `sync_to_extreme_nightly.ps1` | Backup utility | LEGACY | ARCHIVE |
| `JetFighter_Launch_Compliance.bat` | Old Windows launcher | LEGACY | ARCHIVE |
| `validation-e2e-production.csv` | Validation data | TEMPORARY | ARCHIVE |
| `pilot_restore_point.md` | Pilot docs | TEMPORARY | MOVE to docs/ |
| `ORGANISM_CONSTITUTION_AUDIT.md` | Audit docs | TEMPORARY | MOVE to docs/ |
| `.commit_msg.txt` | Git helper | TEMPORARY | GITIGNORED |

---

## PHASE 6 — ENVIRONMENT AUDIT

### .env Handling

| File | Gitignored | Contains Secrets | Risk |
|------|------------|------------------|------|
| `.env` | ✅ YES | Yes (SMTP, tokens) | LOW |
| `.ops_env` | ✅ YES | Yes (OPS_PASSWORD) | LOW |
| `.env.*` | ✅ YES | Potentially | LOW |

### .gitignore Coverage

| Category | Pattern | Coverage |
|----------|---------|----------|
| Virtual env | `.venv/` | ✅ Covered |
| Cache | `__pycache__/`, `.pytest_cache/` | ✅ Covered |
| Env files | `.env`, `.env.*`, `.ops_env` | ✅ Covered |
| Logs | `*.log` | ✅ Covered |
| Data | `data/*` with exceptions | ✅ Covered |
| Cloudflare | `.cloudflared/`, `bin/cloudflared.exe` | ✅ Covered |
| Node | `vio-frontend/node_modules/` | ✅ Covered |
| Databases | `*.sqlite3` | ✅ Covered |

### Secrets Exposure Risk

| Risk Area | Status | Notes |
|-----------|--------|-------|
| API keys in code | ✅ SAFE | Keys loaded from env |
| Passwords in code | ✅ SAFE | Passwords loaded from env |
| Tokens in code | ✅ SAFE | Tokens loaded from env |
| Secrets in .gitignore | ✅ COVERED | All secret files excluded |
| Secrets in logs | ⚠️ CHECK | Logs are gitignored but some exist |

**Overall:** LOW RISK — gitignore coverage is comprehensive.

---

## PHASE 7 — RISK REPORT

### CRITICAL (0)

None identified.

### HIGH (2)

| Risk | Location | Impact |
|------|----------|--------|
| **Tracked log files** | Root (*.log files exist) | Log files are gitignored but some may be tracked from before |
| **Untracked PDF deletions** | Root (SOSWY_*.pdf) | Business documents were in repo; deletions unstaged |

### MEDIUM (4)

| Risk | Location | Impact |
|------|----------|--------|
| **Root clutter** | 5 TXT files, 9 JSON files, 7+ scripts | Confusing repository structure |
| **Duplicate startup scripts** | 4 scripts doing similar things | Operator confusion |
| **Inconsistent ports** | start_everything uses 8000, others 8080 | Potential misconfiguration |
| **Orphaned pilot files** | pilot_*.json, pilot_restore_point.md | Should be archived or moved to docs/ |

### LOW (5)

| Risk | Location | Impact |
|------|----------|--------|
| **drafts/ folder** | Single file telemetry_fastapi_endpoint.py | Unused code |
| **organism/ sqlite** | Legacy organism database | Not production truth (documented) |
| **Empty New Text Document.txt** | Root | Clutter |
| **.vio_brief/** | VIO cursor brief | Could be archived |
| **tests_archived/** | Archived VIO tests | Properly archived, low risk |

---

## PHASE 8 — RECOMMENDATIONS

### SAFE TO KEEP

| Item | Reason |
|------|--------|
| `AGENTS.md` | Binding documentation |
| `Dockerfile` | Production deployment |
| `render.yaml` | Production deployment |
| `requirements.txt` | Dependencies |
| `server.py` | Application entry |
| `pytest.ini` | Test configuration |
| `.gitignore` | Essential |
| `services/` | Core business logic |
| `tests/` | Test suite |
| `docs/` | Documentation |
| `ui/` | User interface |
| `scripts/` | Operator tools |
| `organism_core/` | Organism adapter |
| `schemas/` | Data schemas |
| `.github/` | CI/CD |
| `archive/` | Historical (properly contained) |
| `tests_archived/` | Historical (properly contained) |

### SAFE TO MOVE

| Item | Current | Recommended |
|------|---------|-------------|
| `audit_companies.py` | Root | `archive/dev_tools/` |
| `generate_qr.py` | Root | `scripts/` |
| `pilot_restore_point.md` | Root | `docs/` |
| `ORGANISM_CONSTITUTION_AUDIT.md` | Root | `docs/` |
| `.vio_brief/` | Root | `archive/` |
| `drafts/telemetry_fastapi_endpoint.py` | drafts/ | `archive/dev_tools/` |

### SAFE TO ARCHIVE

| Item | Reason |
|------|--------|
| `A) Autostart the tunnel (uses your.txt` | Old operator notes |
| `export latest project's binder (avoid $pid).txt` | Old one-liner |
| `go to the right folder (PS5-safe).txt` | Old one-liner |
| `One-liner to open the Control Panel.txt` | Old one-liner |
| `dns_reset_and_audit.ps1` | Legacy utility |
| `stage1_install.ps1` | Legacy installer |
| `sync_to_extreme_nightly.ps1` | Legacy backup |
| `JetFighter_Launch_Compliance.bat` | Legacy launcher |
| `start_everything.ps1` | Duplicate of start_production |
| `start_live_platform.ps1` | Duplicate of start_production |
| `fix_everything.ps1` | Duplicate functionality |
| `pilot_*.json` (all 5 files) | Pilot phase artifacts |
| `*_report.json` (all audit reports) | Temporary audit outputs |
| `validation-e2e-production.csv` | Temporary validation data |

### NEEDS INVESTIGATION

| Item | Question |
|------|----------|
| `organism/` directory | Is any code still referencing this? Can it be archived? |
| Log files in root | Are any being tracked? Run `git ls-files *.log` to verify |
| Deleted PDFs | Should these be committed as deletions? |

---

## SUMMARY

| Category | Count |
|----------|-------|
| Directories (root) | 21 |
| Files (root) | 52 |
| Production files | 8 |
| Development files | 12 |
| Legacy/Archive candidates | 22 |
| Clutter items | 10+ |

### Repository Health

| Metric | Status |
|--------|--------|
| Core production files | ✅ Clean |
| Documentation | ✅ Current (post-audit) |
| Test suite | ✅ Active |
| Archive structure | ✅ Proper |
| Gitignore coverage | ✅ Comprehensive |
| Root clutter | ⚠️ Needs cleanup |
| Duplicate scripts | ⚠️ Needs consolidation |
| Secrets exposure | ✅ Low risk |

---

## NO MODIFICATIONS MADE

This is an audit document only. All recommendations require owner approval before implementation.
