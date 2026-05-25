# Public UI Exposure Audit

**Date:** 2026-05-25  
**Scope:** All files under `ui/`  
**Mission:** Ensure customer-facing pages do not expose internal operator consoles, APIs, or diagnostic terminology.

## Classification

### Public (customer-safe)

| Page | Role |
|------|------|
| `ui/shop.html` | Service catalog landing |
| `ui/inquiry.html` | Readiness review / contact |
| `ui/intake.html` | Tokenized client intake |
| `ui/upload.html` | Evidence upload |
| `ui/index.html` | Static mount smoke test → services |
| `ui/vendor_quote.html` | Vendor RFQ submission |

**Allowed public nav:** Services (`shop.html`), Readiness review (`inquiry.html`), Contact (`inquiry.html` on intake/upload), Upload flow links only where relevant.

### Internal (operator-only)

| Page | Role |
|------|------|
| `ui/control.html` | Operator cockpit |
| `ui/command.html` | Command center |
| `ui/memory.html` | Central intelligence / organism telemetry |
| `ui/knowledge.html` | Knowledge base ops |
| `ui/webhook_test.html` | Webhook kickoff test harness |
| `ui/status.html` | Project status board |
| `ui/inbox.html` | Operator inbox |
| `ui/scan.html` | Scan tooling |
| `ui/event.html` | Event inspector |
| `ui/healthz.html` | System health |
| `ui/lead_discovery.html` | Lead discovery |
| `ui/onboarding_validation.html` | Onboarding validation |
| `ui/new_client.html` | New client ops |
| `ui/readiness/*.html` (8 pages) | Live-assessment operator scripts |

**Required internal nav:** Control, Command, Status, Inbox, Intelligence, Knowledge, Public site.

## Violations Found & Fixed

### Public pages (pre-audit)

| Location | Violation | Fix |
|----------|-----------|-----|
| `ui/shop.html` | Previously linked Operations Console (commit 7e7e010) | Already removed; verified clean |
| `ui/inquiry.html` | — | No internal links found |
| `ui/intake.html` | — | No internal links found |
| `ui/upload.html` | — | No internal links found |
| `ui/index.html` | — | Links only to `shop.html` |
| `ui/vendor_quote.html` | — | Public nav only |

### Internal pages linked from non-operator surfaces

| Location | Violation | Fix |
|----------|-----------|-----|
| `ui/readiness/*.html` (8 files) | Ops nav + back link to `control.html` exposed on URLs reachable without auth | Added `noindex,nofollow`; standardized full operator nav; pages remain operator-only (not linked from public) |
| `ui/memory.html` | Non-standard nav (Cockpit, Lead discovery) | Standardized operator nav |
| `ui/knowledge.html` | Partial nav | Standardized operator nav |
| `ui/webhook_test.html` | Missing Intelligence/Knowledge | Standardized operator nav |
| `ui/lead_discovery.html` | Single Control link | Standardized operator nav |
| `ui/onboarding_validation.html` | Single Control link | Standardized operator nav |
| All 21 internal HTML pages | Missing `noindex,nofollow` | Added robots meta |

### Patterns audited (no public exposure after fix)

- `Operations Console`, `/ui/control.html`, `/ui/memory.html`, `/ui/command.html`, `/ui/webhook_test.html`
- `/api/memory/`, `/api/ops/`
- Terms: organism, telemetry, self-heal, observability, internal diagnostic, operations console

Public pages retain legitimate compliance wording (e.g. “Access Control”, “AI controls”, “audit-ready operations”) — not operator-console references.

## Automated enforcement

| File | Purpose |
|------|---------|
| `tests/test_public_ui_exposure.py` | Comprehensive public/internal classification tests |
| `tests/test_public_ops_links.py` | Back-compat re-exports from exposure suite |
| `scripts/patch_internal_ui_nav.py` | One-shot noindex + nav standardization (reference) |

Run: `python -m pytest tests/ -q`

## Manual review still recommended

| Item | Reason |
|------|--------|
| `ui/*.backup*.html`, `ui/*.bak` | Legacy backups still under `/ui` static mount; not in test scope; consider moving out of `ui/` |
| `ui/readiness/*.html` | Operator assessment scripts — noindexed but URL-guessable; consider auth gate or robots.txt disallow |
| `ui/assets/js/organism-intel.js` | Internal API client; only loaded by operator pages — verify no public page imports it |
| Auth on `/ui/control.html` et al. | UI hardening is link/SEO layer only; server-side access control is separate |

## Summary

- **Public pages:** 6 classified; 0 internal link violations remaining.
- **Internal pages:** 21 hardened with `noindex,nofollow` and consistent operator navigation.
- **Tests:** 151 passed (`test_public_ui_exposure.py` adds 51 parametrized checks).
