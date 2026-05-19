# KYC UI Lane 2 Consolidation

**Date:** 2026-05-19  
**Task:** 12 — Secondary ops/readiness pages + deploy visual QA  
**Mode:** Stabilization — CSS/shell only, no backend changes

---

## 1. Full UI inventory (`ui/`)

| Path | Classification | Audience | Lane 1 | Lane 2 |
|------|----------------|----------|--------|--------|
| `shop.html` | Unified | Public | Yes | — |
| `inquiry.html` | Unified | Public | Yes | — |
| `intake.html` | Unified (+ compat CSS) | Public | Yes | — |
| `upload.html` | Unified | Public | Yes | — |
| `control.html` | Unified | Ops | Yes | — |
| `command.html` | Unified | Ops | Yes | — |
| `status.html` | Unified | Ops / client status | — | **Yes** |
| `inbox.html` | Unified | Ops queue | — | **Yes** |
| `event.html` | Unified | Ops CoC entry | — | **Yes** |
| `scan.html` | Unified | Ops mobile scan | — | **Yes** |
| `new_client.html` | Unified | Ops | — | **Yes** |
| `webhook_test.html` | Unified | Ops internal | — | **Yes** |
| `vendor_quote.html` | Unified | Vendor / RFQ | — | **Yes** |
| `healthz.html` | Unified | Ops diagnostic | — | **Yes** |
| `index.html` | Unified | Internal smoke | — | **Yes** |
| `readiness/index.html` | Unified | Ops consultant | — | **Yes** |
| `readiness/script.html` | Unified | Ops consultant | — | **Yes** |
| `readiness/questions.html` | Unified | Ops consultant | — | **Yes** |
| `readiness/scoring.html` | Unified | Ops consultant | — | **Yes** |
| `readiness/report.html` | Unified | Ops consultant | — | **Yes** |
| `readiness/outreach.html` | Unified | Ops consultant | — | **Yes** |
| `readiness/pre-call.html` | Unified | Ops consultant | — | **Yes** |
| `readiness/follow-up.html` | Unified | Ops consultant | — | **Yes** |
| `intake.js` | Asset (script) | Public | Unchanged | — |
| `assets/styles/*.css` | Shared foundation | All | Task 11 | + `readiness-compat.css` |
| `*.backup*.html` | Legacy backup | **Unused** | No | **Not modified** |
| `intake.before-*.html` | Legacy backup | **Unused** | No | **Not modified** |
| `command.html.*.bak` | Legacy backup | **Unused** | No | **Not modified** |

**Counts:** 22 active HTML surfaces unified (6 Lane 1 + 16 Lane 2). 12+ backup files left untouched.

---

## 2. Pages unified in Lane 2

### Operations

| Page | Role | Shell |
|------|------|-------|
| `status.html` | Project/step status, RFQ, vendors | Ops topbar + `#list` / `#detail` |
| `inbox.html` | Live project queue + toast alerts | `#tbl`, `#count`, `#toast`, 10s refresh |
| `event.html` | Chain-of-custody form | `#f`, `#project_id`, `#tbl`, `/api/coc/event/form` |
| `scan.html` | Camera barcode + event submit | `#cam`, `#f`, BarcodeDetector, same CoC API |
| `new_client.html` | Manual kickoff | `#f`, `#ref`, `#email`, `/events/payment/test` |
| `webhook_test.html` | Test kickoff | `#out`, `/api/test-webhook` |
| `vendor_quote.html` | RFQ vendor response | `#f`, `#token`, `/api/rfq/submit` |
| `healthz.html` | JSON health viewer | `#status`, `#json`, `/healthz` |
| `index.html` | Static mount check | Link to shop |

### Readiness (`ui/readiness/`)

All 8 pages: shared dark theme, large `.codebox` text, ops nav, section nav between readiness files, back link to `control.html`. **Content preserved** (consultant scripts unchanged).

---

## 3. Shared CSS used

| File | Used by |
|------|---------|
| `design-system.css` | All unified pages |
| `layout.css` | All unified pages |
| `components.css` | All unified pages (+ RAG badges, toast, scan video) |
| `ops-dashboard.css` | Ops pages (status, inbox, event, scan, control, command, …) |
| `intake-compat.css` | `intake.html` only |
| `readiness-compat.css` | `readiness/*` only |

No second design language introduced.

---

## 4. Functional hooks preserved

| Page | Preserved |
|------|-----------|
| `status.html` | `load()`, `show(pid)`, `advance()`, `launchRFQ()`, `/api/projects`, `/api/project/{id}/status`, `/api/project/{id}/advance`, `/api/rfq/create` |
| `inbox.html` | `refresh()`, `#tbl`, `localStorage` prevProjects, `/api/projects`, `/api/project/{id}/status` |
| `event.html` | `#f`, `#project_id`, `#event_type`, `#refresh`, `#tbl`, `POST /api/coc/event/form`, `/api/events/recent` |
| `scan.html` | Full camera script, `#useCode`, `#geo`, `#submit`, `POST /api/coc/event/form` |
| `new_client.html` | `#ref`, `#email`, `#name`, SKU checkboxes, `POST /events/payment/test` |
| `webhook_test.html` | `send()`, `POST /api/test-webhook` |
| `vendor_quote.html` | `token` query param, `POST /api/rfq/submit` |
| `readiness/*` | Static content only; navigation links between readiness files |

---

## 5. Deploy visual QA (Render)

**Host probed:** `https://jetfighter-compliance.onrender.com`  
**When:** 2026-05-19 (local Lane 2 changes **not yet deployed** to this host)

### CSS assets

| URL | Result |
|-----|--------|
| `/ui/assets/styles/design-system.css` | **404** |
| `/ui/assets/styles/layout.css` | **404** |
| `/ui/assets/styles/components.css` | **404** |
| `/ui/assets/styles/ops-dashboard.css` | **404** |
| `/ui/assets/styles/readiness-compat.css` | **404** |

### HTML pages (HTTP 200, pre-deploy content)

| URL | Status | `design-system.css` in HTML |
|-----|--------|----------------------------|
| `/ui/shop.html` | 200 | **No** (live = pre–Task 11/12 deploy) |
| `/ui/inquiry.html` | 200 | No |
| `/ui/intake.html` | 200 | No |
| `/ui/upload.html` | 200 | No |
| `/ui/control.html` | 200 | No |
| `/ui/command.html` | 200 | No |
| `/ui/status.html` | 200 | No |
| `/ui/inbox.html` | 200 | No |
| `/ui/event.html` | 200 | No |
| `/ui/scan.html` | 200 | No |
| `/ui/readiness/index.html` | 200 | No |

### Verdict

**Local repo:** Lane 2 complete — all target pages reference shared CSS.  
**Live Render:** Visual QA **blocked until deploy** pushes `ui/assets/styles/` and updated HTML. After deploy, re-run:

```powershell
$base = "https://jetfighter-compliance.onrender.com"
@(
  "/ui/assets/styles/design-system.css",
  "/ui/shop.html",
  "/ui/status.html",
  "/ui/readiness/index.html"
) | ForEach-Object {
  $r = Invoke-WebRequest "$base$_" -UseBasicParsing
  Write-Host $_.PadRight(45) $r.StatusCode
}
```

Expect CSS **200** and HTML containing `design-system.css`.

---

## 6. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| CSS 404 on live until deploy | **High** (visual) | Deploy `jetfighter_compliance` to Render |
| Readiness duplicate “back” links | Low | Cosmetic; remove duplicate in Lane 3 |
| `command.html` UTF-8 BOM | Low | Re-save UTF-8 without BOM if garbled |
| Backup HTML still in repo | None | Not served in normal flows |
| Custom domain not on backend | Ops | Task 9 / Owner DNS (unchanged) |

---

## 7. Remaining gaps (post–Lane 2)

| Item | Status |
|------|--------|
| Backup `*.backup*.html` | Intentionally legacy |
| Live CSS delivery | **Pending deploy** |
| Custom domain visual QA | Pending `keepyourcontracts.com` → backend |
| Browser console / mobile pass | Post-deploy manual check |
| `intake-compat.css` long-term | Optional merge into components when intake markup refactored |

---

## 8. Helper scripts (repo)

| Script | Purpose |
|--------|---------|
| `scripts/lane2_unify_ui.py` | Regenerate Lane 2 ops pages (idempotent) |
| `scripts/fix_motion_tags.py` / `scrub_motion.py` | HTML tag cleanup utilities |

---

## 9. Approved next lane

**Lane 3 (post-deploy):** Re-run visual QA on Render + custom domain; optional backup HTML archive; remove duplicate readiness back links.

**Do not** change onboarding/evidence backend without explicit Owner task.
