# KYC Unified Design System

**Version:** 1.0 (Task 11 — Stabilization)  
**Scope:** `jetfighter_compliance/ui` public + operations surfaces  
**Stack:** Plain HTML + shared CSS (no React/Vue, no new frameworks)

---

## Design intent

One operational organism identity: **enterprise compliance operations**, not startup SaaS or generic admin templates.

| Principle | Rule |
|-----------|------|
| Calm | Restrained color, deliberate whitespace |
| Trust | Operational labels, status clarity, audit-ready tone |
| Deterministic | Clear step hierarchy on onboarding flows |
| Serious | No gimmicks, gradients-for-show, or over-animation |

Visual direction: Palantir / Deloitte cyber / secure ops dashboards — **dark operational surface**, accent blue, muted secondary text.

---

## File structure

| Asset | Role |
|-------|------|
| `ui/assets/styles/design-system.css` | Tokens, typography, base reset |
| `ui/assets/styles/layout.css` | Topbar, hero, sections, grids, footer |
| `ui/assets/styles/components.css` | Cards, buttons, forms, tables, status, legacy `.btn`/`.card` aliases |
| `ui/assets/styles/ops-dashboard.css` | Control + command panels, metrics, lists |
| `ui/assets/styles/intake-compat.css` | Maps legacy intake class names to tokens |

**Load order:** `design-system` → `layout` → `components` → (`ops-dashboard` \| `intake-compat`)

---

## Typography

| Token | Value | Use |
|-------|-------|-----|
| `--kyc-font` | Segoe UI, system-ui, Inter stack | All UI copy |
| `--kyc-mono` | ui-monospace stack | `code`, IDs |
| `--kyc-text-hero` | clamp(2rem, 4vw, 3.25rem) | Page H1 |
| `--kyc-text-3xl` | 1.875rem | Section H2 |
| `--kyc-text-2xl` | 1.5rem | Card H3 |
| `--kyc-text-base` | 1rem | Body |
| `--kyc-text-sm` | 0.875rem | Nav, meta |
| `--kyc-text-xs` | 0.75rem | Overlines, pills |
| `--kyc-tracking-label` | 0.06em | Operational labels (uppercase) |

**Rules:**

- One H1 per page; section titles use H2/H3.
- Body copy uses `--kyc-text-muted`; avoid long unbroken paragraphs on intake/upload.
- Overlines: `.kyc-label-overline` for “Service catalog”, “Runtime status”, etc.

---

## Spacing

4px base scale via `--kyc-space-*` (1–16).

| Context | Token |
|---------|--------|
| Card padding | `--kyc-space-8` |
| Section vertical rhythm | `--kyc-space-12` |
| Form field gap | `--kyc-space-5` |
| Nav gap | `--kyc-space-6` |

**Container widths:**

- `--kyc-container` (72rem) — default main
- `--kyc-container-narrow` (40rem) — inquiry, upload
- `--kyc-container-wide` (80rem) — shop

---

## Color

| Token | Hex | Use |
|-------|-----|-----|
| `--kyc-bg` | #060d18 | Page background |
| `--kyc-surface` | #0f1c2e | Cards, panels |
| `--kyc-line` | #1f3250 | Borders |
| `--kyc-text` | #f4f7fb | Primary text |
| `--kyc-text-muted` | #9eb4d1 | Secondary |
| `--kyc-accent` | #1f7cff | Primary actions |
| `--kyc-success` | #14c784 | OK / evidence step |
| `--kyc-warning` | #ffb020 | Degraded |
| `--kyc-danger` | #ef4444 | Error / down |

**Rules:**

- Accent for **one** primary CTA per viewport section.
- Status colors only for health, pills, and alerts — not decorative fills.
- No bright gradients on buttons (intake submit is solid accent).

---

## Components

### Navigation (`.kyc-topbar`)

- Brand: `Keep` + accent `YourContracts`
- Public: Services, Contact
- Ops (control/command): Control, Command, Public site

### Buttons (`.kyc-btn`)

- `--primary` — single main action
- `--secondary` — outline
- `--block` — full-width form submit
- Legacy `.btn` / `.btn.secondary` — control panel (same tokens)

### Cards (`.kyc-card`, `.kyc-card--flat`)

- Gradient surface, `--kyc-line` border, `--kyc-radius-xl`
- Flat variant for dense grids (shop, ops actions)

### Forms (`.kyc-field`, `.kyc-form-grid`, `.kyc-check`)

- Dark inset inputs, focus ring via `--kyc-accent-soft`
- Checkbox grid for intake external requirements

### Status

- `.kyc-pill` / `.kyc-pill--ok|warn|bad` — health, pub host
- `.kyc-status` / `--ok` / `--error` — form feedback
- `.kyc-badge` — page role label (e.g. “Guided onboarding”)

### Trust

- `.kyc-trust-item` — sidebar proof points (intake)
- `.kyc-flow-step` — inquiry → intake → upload progression

### Ops dashboard

- `.panel`, `.metric-card`, `.status-tile`, `.list` — command center (aliases in `ops-dashboard.css`)

---

## Layout rules

1. Every page: `body.kyc-page` + `.kyc-topbar` + `main` + `.kyc-footer` (or ops header + main).
2. Public marketing: `.kyc-hero` → `.kyc-section` with `.kyc-grid--3`.
3. Onboarding: narrow main + `.kyc-flow-steps` + single primary card.
4. Ops: `.kyc-ops-header` + `.kyc-main--ops` + action grid.

---

## Page roles

| Page | Role | Pattern |
|------|------|---------|
| `shop.html` | Product / service entry | Hero split + service catalog |
| `inquiry.html` | Qualification + contact | Flow steps + short form |
| `intake.html` | Compliance intake | Two-column form + trust/QR |
| `upload.html` | Evidence collection | Flow step 3 active + upload zone |
| `control.html` | Ops monitoring hub | Status + action cards + project table |
| `command.html` | Admin command surface | Health / projects / events panels |

---

## Trust language

Use operational vocabulary:

- “Evidence”, “intake”, “workflow”, “audit-ready”, “secure submission”
- Avoid: “awesome”, “supercharge”, “rocket”, playful emoji
- Step labels: **Step 1 — Inquiry** (not “Get started!”)

---

## UX rules

1. **One primary CTA** per screen region.
2. **Show flow position** on inquiry, intake, upload.
3. **Feedback** via `#msg` / `#status` with `.kyc-status--ok|--error`.
4. **Do not** change form `name`, `id`, or API paths when styling.
5. **Mobile:** grids collapse at 900px; topbar wraps.

---

## Forbidden patterns

- Inline `<style>` blocks on canonical pages (use shared CSS)
- Duplicate topnav injections
- Light gray “SaaS template” ops theme mixed with dark public pages
- iOS-blue default buttons (`#0a84ff`) without tokens
- New CSS frameworks or build pipelines for this task
- Renaming form fields or breaking `/api/*` hooks

---

## Extension

New UI pages must:

1. Link the three core stylesheets minimum.
2. Use `.kyc-topbar` and container classes.
3. Add page-specific rules only in a new file under `ui/assets/styles/` if unavoidable — prefer reusing components.

All active pages under `ui/` (except backups) use this system as of **Task 12**. See `docs/KYC_UI_LANE2_CONSOLIDATION.md` for inventory and deploy QA.
