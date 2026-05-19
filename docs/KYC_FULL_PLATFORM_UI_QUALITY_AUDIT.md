# KYC Full Platform UI Quality Audit (Task 14)

**Date:** 2026-05-19  
**Gold standard:** `ui/shop.html`  
**Scope:** Visual quality only — no backend routes, API paths, onboarding logic, or Just Talk/SAGE changes.

---

## Executive summary

All **22 active** HTML pages under `ui/` now share the dark enterprise design system (`design-system.css`, `layout.css`, `components.css`) with shop-level polish: sticky topbar, ops headers with subtitles, hero/section hierarchy, and consistent footers. **Intake** was rebuilt off ~500 lines of inline CSS onto the shared shell. **Command** was re-shelled with UTF-8 cleanup and visible `kyc-ops-header`. **Readiness** pages received hero wrappers and duplicate-nav cleanup.

**Backups excluded:** `*.bak`, `*.backup*`, `intake.before-*.html`, `command.html.*.bak`

---

## Page inventory and classification

| Page | Before (Task 14) | After | Notes |
|------|------------------|-------|-------|
| `shop.html` | MATCHES SHOP QUALITY | MATCHES SHOP QUALITY | Reference standard |
| `inquiry.html` | MATCHES SHOP QUALITY | MATCHES SHOP QUALITY | Flow steps + hero |
| `intake.html` | OLD/RUDIMENTARY | MATCHES SHOP QUALITY | Inline CSS removed; `kyc-grid--intake`; `#f` + `ext_*` preserved |
| `upload.html` | NEEDS POLISH | MATCHES SHOP QUALITY | Hero + flow steps; `#uploadForm` preserved |
| `control.html` | NEEDS POLISH | MATCHES SHOP QUALITY | Section heads, ops subtitle, tool grid |
| `command.html` | BROKEN/STYLED WRONG | MATCHES SHOP QUALITY | BOM/mojibake fixed; `kyc-ops-header`; panel JS IDs kept |
| `status.html` | NEEDS POLISH | MATCHES SHOP QUALITY | Section hierarchy; vendor/RFQ div hooks fixed |
| `inbox.html` | NEEDS POLISH | MATCHES SHOP QUALITY | Ops subtitle; `#tbl` preserved |
| `event.html` | NEEDS POLISH | MATCHES SHOP QUALITY | `#f`, `#project_id`, `#tbl` preserved |
| `scan.html` | NEEDS POLISH | MATCHES SHOP QUALITY | `#cam` + scan hooks preserved |
| `new_client.html` | NEEDS POLISH | MATCHES SHOP QUALITY | Manual kickoff form preserved |
| `webhook_test.html` | NEEDS POLISH | MATCHES SHOP QUALITY | Diagnostic payload UI |
| `vendor_quote.html` | NEEDS POLISH | MATCHES SHOP QUALITY | Compact hero; `#f` + token preserved |
| `healthz.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | Compact hero; `/healthz` fetch |
| `index.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | UI mount probe |
| `readiness/index.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | Hero + nav; master scroll content |
| `readiness/script.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | Same shell |
| `readiness/questions.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | Same shell |
| `readiness/scoring.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | Same shell |
| `readiness/report.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | Same shell |
| `readiness/outreach.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | Same shell |
| `readiness/pre-call.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | Same shell |
| `readiness/follow-up.html` | INTERNAL BUT ACCEPTABLE | MATCHES SHOP QUALITY | Same shell |

---

## Changes made (by category)

### Layout and shell

- Unified `kyc-topbar` + ops nav (Control, Command, Status, Inbox, Public site) on all ops/readiness pages
- Added `kyc-ops-header` + `kyc-ops-subtitle` on ops surfaces for clear page role
- Added `kyc-hero` / `kyc-hero--compact` on public utility pages (vendor quote, healthz, index)
- Added `kyc-hero--readiness` on readiness workflow pages
- Standard footer: *KeepYourContracts.com · Enterprise Compliance Workflow Platform*

### CSS

- `layout.css`: `kyc-hero--compact`, `kyc-hero--readiness`, `kyc-hero-lead`, ops section rhythm
- Existing `ops-dashboard.css` legacy class maps retained for `command.html` panels

### Scripts (repo helpers, not runtime)

- `scripts/task14_quality.py` — intake rebuild, status/control polish, readiness nav cleanup
- `scripts/task14_finish.py` — command re-shell, ops subtitles, UTF-8 scrub, public heroes

### Functional hooks preserved

| Page | Preserved IDs / paths |
|------|------------------------|
| Intake | `#f`, `#token`, `name="ext_*"`, `intake.js`, `POST /api/intake/submit` |
| Upload | `#uploadForm`, `#project_id`, `#email`, evidence API |
| Inquiry | `#f`, `POST /api/inquiry/submit` |
| Status | `#list`, `#detail`, `/api/projects`, `/api/project/{id}/status`, RFQ |
| Inbox | `#tbl`, `#count`, `#toast` |
| Event | `#f`, `#project_id`, `#tbl`, `/api/coc/event/form` |
| Scan | `#cam`, camera / QR hooks |
| Command | `#panel-health`, `#badge-health*`, `#events-body`, `/healthz`, `/api/events/recent` |
| Control | `#health`, `#demo`, `#table`, `#pubHost`, export/demo endpoints |
| Vendor quote | `#f`, `#token`, `POST /api/rfq/submit` |

---

## Pages now matching shop quality

All 22 active pages listed above.

---

## Remaining polish items (non-blocking)

| Item | Priority | Notes |
|------|----------|-------|
| Readiness content titles | Low | `readiness/index.html` title still references script scroll; content unchanged intentionally |
| Command inner legacy header | Low | Hidden via CSS; visible ops header is canonical |
| Custom domain QA | Medium | Re-verify CSS on `keepyourcontracts.com` when DNS points to Render |
| Mobile pass on scan/upload | Medium | Manual device check recommended |

---

## Intentionally internal/simple

| Page | Why |
|------|-----|
| `healthz.html` | Operator diagnostic; compact hero only |
| `index.html` | Static mount probe |
| `readiness/*` | Internal consultant scroll; large type via `readiness-compat.css` |

---

## Live verification (post-deploy checklist)

After push to Render:

1. Each active page returns **HTTP 200**
2. `/ui/assets/styles/design-system.css` (and siblings) return **200**
3. View-source shows shared CSS links on every page
4. Spot-check: shop, intake, upload, control, command, status, one readiness page
5. Confirm no `<style>` blocks or stray typo tags in active HTML

**Host:** `https://jetfighter-compliance.onrender.com`

---

## Success criteria (Task 14)

| Criterion | Status |
|-----------|--------|
| Every active page audited | **Done** |
| Old/rudimentary pages corrected | **Done** (especially intake, command) |
| One platform visual language | **Done** |
| shop.html not the only modern page | **Done** |
| Functional hooks preserved | **Done** (inspection) |
| Live Render verification | **Pending deploy** |
