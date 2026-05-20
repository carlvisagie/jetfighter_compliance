# KYC Positioning Refinement (Task 23)

**Date:** 2026-05-19  
**Scope:** Copy-only on `ui/shop.html` and `ui/inquiry.html`. No backend, PayPal, QR, or flow changes.

---

## Positioning shift

| Before | After |
|--------|--------|
| Elite / expert-guided compliance consulting | Structured readiness support |
| “Pass your audit” outcome promise | “Show us what you have — understand where you stand” |
| Enterprise omniscience / 24/7 expert ops | Evidence organization, gap visibility, guided workflows |
| Book a diagnostic / contact & qualification | Upload & readiness review |
| Implied authority to certify or pass audits | Operational assistance; no approval guarantees |

**Core idea (primary):**  
*Show us what you have. We help you understand where you stand.*

**Secondary themes:** organize evidence · identify gaps · structure documentation · reduce chaos · onboarding assistance.

---

## Page changes

### `ui/shop.html`

| Element | Before | After |
|---------|--------|--------|
| Title | Compliance Operations | Structured Compliance Readiness |
| Badge | Expert-Guided GovCon Compliance | Structured readiness support |
| H1 | Pass Your Audit. Keep Your Contracts. | Show us what you have. We help you understand where you stand. |
| Hero body | Expert/consulting tone | Required readiness visibility lines + workflow support |
| Primary CTA | Schedule Diagnostic Review | Begin readiness review |
| Hero aside | 24/7 expert, audit-ready, enterprise | Evidence, gaps, structure, guided |
| Catalog | Core Services | Readiness programs |
| Outcomes | Expert guidance at scale | Organize evidence / identify gaps / reduce chaos |
| Footer tagline | Enterprise Compliance Workflow Platform | Structured compliance readiness assistance |

### `ui/inquiry.html`

| Element | Before | After |
|---------|--------|--------|
| Title | Contact & Qualification | Upload & Readiness Review |
| Nav | Contact | Readiness review |
| Badge | Guided onboarding | Readiness visibility |
| H1 | Contact & qualification | Upload & readiness review |
| Hero | Generic inquiry | Upload + readiness visibility messaging |
| Form heading | Send message | Tell us what you have |
| Submit button | Submit inquiry | Submit readiness review |

**Preserved:** `#f`, `/api/inquiry/submit`, flow steps, PayPal QR `<details>` block, all hooks.

---

## Trust rationale

- **Grounded promise:** Describes what the platform does (organize, structure, surface gaps) instead of what it cannot guarantee (certification, government endorsement, audit pass).
- **Invites evidence:** “Show us what you have” sets correct expectations — client brings materials; platform assists with visibility.
- **No false authority:** Removes language that sounds like a C3PAO, certifying body, or omniscient AI compliance oracle.

---

## Liability reduction rationale

Removed or avoided:

- Guaranteed audit outcomes (“pass your audit”)
- Certification authority framing
- “Expert-guided” / “enterprise” puff that implies regulated endorsement
- Outcome certainty in outcomes section (replaced with “not a promise of approval” where relevant)

Retained factual service names (e.g. CMMC Readiness Assessment) as **program labels**, not claims of official assessment authority.

---

## Conversion rationale

- **Lower friction:** “Readiness review” and “begin readiness review” feel like a concrete first step, not a sales call.
- **Clear deliverable:** Structured visibility and organization are believable deliverables worth paying for.
- **Trust before pay:** Inquiry path emphasizes upload/review; PayPal path unchanged for those ready to purchase a program.

---

## Future evolution path

1. **Phase A (current):** Readiness visibility + evidence workflow + manual/ops-assisted kickoff.  
2. **Phase B:** PayPal webhook → automated kickoff; tighten post-pay copy to match positioning.  
3. **Phase C:** Optional readiness score/report language aligned with internal `readiness/*` scripts (already disclaim “not certification”).  
4. **Phase D:** Custom domain live + owner env lock; same copy on branded host.

Do not reintroduce “expert elite” or “guaranteed compliance” language in marketing without legal review.

---

## Live verification (Render)

| URL | Check | Result |
|-----|-------|--------|
| `/ui/shop.html` | New H1 + no “Expert-Guided” badge | **PASS** |
| `/ui/inquiry.html` | “Upload & readiness review” | **PASS** |
| PayPal / QR | Unchanged | **PASS** |

**Deploy commit:** `1380989` on `origin/main`.

---

## Success criteria

| Criterion | Status |
|-----------|--------|
| Trustworthy, grounded tone | **Done** (copy) |
| No certification/authority implication | **Done** (hero/outcomes) |
| Required messaging lines present | **Done** |
| PayPal, QR, flows preserved | **Done** |
| Live deploy verified | **Pending** |
