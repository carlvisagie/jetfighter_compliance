# VIO Doctrine

> *"Movement is currency. Stillness is health. Shape is the language."*

The Visual Intelligence Observatory (VIO) is the sole command surface of
the KYC platform. It is not a dashboard. It is a **visual cognition
system** — an instrument the operator reads the way an air-defence
console or anaesthesiology monitor is read: at a glance, with subconscious
fluency, and never against a wall of decoration.

This document is the doctrine VIO is built to. Every commit that touches
the VIO layer must hold this charter as the standard of acceptance.

---

## § 1 — Five inviolable principles

1. **Stillness is the baseline.**
   The default state of a healthy organism is calm. No idle pulsing, no
   decorative motion, no "cool cyberpunk animation." If everything moves,
   nothing moves; urgency loses meaning and the operator habituates to
   the noise. Catastrophe must not hide in visual wallpaper.

2. **Movement is currency.**
   Motion is the most expensive resource on the operator's nervous
   system. Spend it only when a real semantic condition warrants
   attention. Every animated element must map to a real deviation; no
   exceptions, no decoration.

3. **Color is semantic.**
   Each colour token names exactly one operational meaning. Colour is
   never aesthetic; colour is *language*. Adding a colour without
   declaring its semantic is forbidden.

4. **Shape is the language.**
   The line itself encodes the story — position, length, density,
   thickness, break, branch. Information that can be conveyed by shape
   must not be duplicated in a badge, pill, column, tab, or list.

5. **Silence is information.**
   When VIO is quiet, the organism is healthy. The absence of motion is
   itself a reading. Operators learn to trust that quietness; do not
   undermine it.

---

## § 2 — The pipeline backbone (the 7-stage spine)

Every company traces through the same backbone:

```
  intake  →  classification  →  validation  →  evidence mapping
         →  review  →  approval  →  conversion
```

Off `evidence mapping`, exactly **one branch** is allowed:

```
  evidence mapping  ──▶  client follow-up
                            │
                            ▼  (re-enters evidence mapping when customer replies)
```

The backbone is canonical and lives in code at:

- Backend constant: `services/vio_overview.STAGE_BACKBONE`
- Frontend constant: `ui/assets/js/vio.js` → `BACKBONE`

Changing the backbone requires changing both, plus the documentation here.

---

## § 3 — Stage states (the visual lexicon)

Each company's live point on its trace carries exactly one of these
**stage states**. Each state has a single permitted visual treatment.

| Token             | Meaning                                       | Visual treatment                              | Motion?            |
| ----------------- | --------------------------------------------- | --------------------------------------------- | ------------------ |
| `healthy`         | progressing cleanly                           | cool teal solid point, normal line weight     | **none**           |
| `stalled`         | sitting in stage > 48h with no movement       | desaturated grey, thinner line                | **none**           |
| `failed`          | extraction failure, proof gate fail, etc.     | sharp red ✕ at live point, line breaks        | **none**           |
| `waiting_client`  | customer must act (gap, follow-up, confirm)   | branch off spine + soft amber, 4s breathe     | **one breathe**    |
| `inconsistent`    | data conflicts / turbulent extraction         | muted purple turbulence (3 offset dots)       | **none**           |
| `done`            | engagement complete (archived)                | dim green, low opacity, sinks to bottom       | **none**           |

The single allowed animation in the entire system is the **4 s
gentle breathe** on `waiting_client`. That is the only motion that
maps to "alive, but the customer must act." Every other deviation is
encoded statically — by shape, by colour, by a break in the line.

If a future contributor finds themselves reaching for an animation,
the answer is almost always **no**. The exception bar is the breathe.

---

## § 4 — Urgency ordering (Level 1)

Companies in Level 1 are sorted by **`urgency_score` descending** — the
worst at the top, the calmest at the bottom, `done` always last.

```
  urgency_score
    = failure_flags     × 1000
    + days_in_stage     × 50
    + gap_count         × 10
    + stale_payment_days × 5
```

`done` companies are pinned to a sentinel score of −1 so they always
sink, but are never hidden — the operator can still revisit them.

The formula is implemented at `services/vio_overview._compute_urgency`.
Tuning the weights is a doctrinal change; it requires a note here.

---

## § 5 — The three levels

| Level | Surface                              | Purpose                                                       | Build status   |
| ----- | ------------------------------------ | ------------------------------------------------------------- | -------------- |
| 0     | Cockpit (`/ui/control.html`)         | Cognitive topology orbs. Upload orb is the entry into VIO.   | shipped        |
| 1     | VIO (`/ui/vio.html`)                 | One company = one continuous line, urgency-sorted, calm.     | shipped        |
| 2     | VIO landscape (click a company line) | Linear left→right immersive landscape, branches only when    | **shipped**    |
|       |                                      | complexity demands it, recursively clickable to atoms.       |                |

### Level 1 anatomy

```
┌─────────────────────────────────────────────────────────────────┐
│  ◉ VIO  search…              [count] [↺] [⚙]                   │
├─────────────────────────────────────────────────────────────────┤
│  G  no active bottleneck  ·  → next: …      q=… intakes=…/…    │  ← organism strip
├─────────────────────────────────────────────────────────────────┤
│ INTAKE  CLASS  VALID  EVIDENCE  REVIEW  APPROVAL  CONVERSION   │  ← backbone legend
├─────────────────────────────────────────────────────────────────┤
│ [SD] Sigma Defense  ─────●╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌  │  ← inconsistent
│ [DM] Delta Mfg      ──────●        ╲╲                          │  ← waiting_client (branch)
│                                       ●client                  │
│ [TS] Theta Systems  ──────────────────────●╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌  │  ← healthy
│ [AA] Apex Aerospace ●╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌  │  ← healthy (new)
│ [OC] Omega Compliance ─────────────────────────────────●        │  ← done (dimmed)
└─────────────────────────────────────────────────────────────────┘
```

Each line is:
- 56 px tall (the rhythm of the calm baseline)
- exactly one continuous SVG trace
- past segment bright, future segment faint dashed
- live point sized + coloured by `stage_state`
- branch only drawn when `on_branch = true`

### Level 2 (the immersive landscape — shipped)

Click a company line on Level 1 → the page is taken over by a full-screen
horizontal landscape whose visible shape *is* the entire story of that
company:

- Company orb anchored on the **left**, larger and quieter than its
  Level 1 counterpart, breathing only when `waiting_client`.
- Linear left→right **spine** through the same seven backbone stages.
  Past stages are filled; the live stage is enlarged; future stages
  are faint dashed. Every stage anchor is itself clickable and surfaces
  "what happens at this stage" in the side panel.
- **Perpendicular branches** sprout up and down from the stages, but
  **only** when there is real data to surface:

  | Branch              | Anchor stage        | Direction | Renders when                       |
  | ------------------- | ------------------- | --------- | ---------------------------------- |
  | context             | `intake`            | above     | customer wrote context or urgent   |
  | identifiers         | `evidence_mapping`  | above     | tech / vendors / compliance found  |
  | service tier        | `approval`          | above     | review_status ≥ approved           |
  | generated paperwork | `conversion`        | above     | any auto-generated file exists     |
  | papers (uploaded)   | `evidence_mapping`  | below     | any file uploaded                  |
  | missing (gaps)      | `evidence_mapping`  | below     | EI flagged missing items           |
  | findings            | `validation`        | below     | failures / unindexed / etc.        |
  | payment             | `approval`          | below     | payment link sent or recorded      |
  | project             | `conversion`        | below     | kickoff project exists             |

  Clean companies (Apex with one uploaded file, no gaps, no findings)
  render as a clean spine plus a single `papers` cluster of one leaf.
  Complex companies (Sigma with vendors, gaps, partial extraction)
  render as a bushy landscape with multiple clusters above and below
  the spine.

- Every leaf has its own **distinct silhouette**: pages with corner-folds
  for uploaded docs, double-bordered pages for generated paperwork,
  dashed empty pages for gaps, triangles for findings, rounded pills for
  identifiers, cards-with-magnetic-band for payment, hexagons for the
  project anchor.

- **Every visual element is clickable**: clicking a leaf opens a side
  panel with the full detail (file metadata + view/download links for
  documents, severity + hint for findings, why-this-matters + example
  for gaps, paid/amount/link for payment, etc.). Clicking the orb or a
  stage anchor surfaces the overview. The side panel has a back button
  so the operator can recurse and return without losing place.

- **Stillness baseline preserved.** The only animation in the entire
  Level 2 surface is the same 4-second breathe on the orb when the
  company is in `waiting_client`. Hover surfaces a 1-px stroke-width
  bump on the leaf — that is the entire interactive treatment.

- ESC, the back chevron, or a click outside the canvas all return the
  operator to Level 1.

Source: `ui/assets/js/vio-level2.js` + the L2 section of
`ui/assets/styles/vio.css`. Contract locked by
`tests/test_vio_level2_contract.py`.

---

## § 6 — Information surfaces

Level 1 has exactly **three** information surfaces. No more.

1. **The line itself** — encodes stage, stage_state, and attention
   density. Read at a glance.
2. **The hover card** — a transient, fixed-position card surfaces the
   2–4 most relevant facts about the company on `mouseenter`. It
   disappears on `mouseleave`. It is never persistent.
3. **The organism strip** — a single calm band above the traces with
   organism health, current bottleneck, and next recommended action.
   When silent, it is silent.

Pills, badges, tabs, sidebars, secondary columns — **forbidden** at
Level 1. They are the surface area that destroyed every dashboard
that came before.

---

## § 7 — Defensive hygiene

VIO is the operator's *single source of truth*. It must never display
garbage even when upstream data is dirty:

- Company names that look like URLs are reduced to the apex domain.
- Whitespace-only names become `"Unknown"`.
- Pasted strings > 120 chars are truncated with an ellipsis.
- A failed organism call yields `available: false` with an explicit
  error — never silent absence.
- A 404 from the composite detail endpoint returns `ok: false` —
  never crashes the front-end.

This logic lives in `services/vio_overview._clean_company_name` and the
corresponding handlers in `server.py`. There is a dedicated test file
at `tests/test_vio_company_name_sanitiser.py`.

---

## § 8 — Test acceptance for Level 1

A change to VIO Level 1 is accepted when an operator can:

1. **Within 3 seconds of opening the page**, identify which company
   needs attention most and what kind of attention (failed? waiting on
   the customer? stalled?).
2. **Without reading any text**, distinguish the five doctrinal
   `stage_state` tokens from each other by shape and colour alone.
3. **Without scrolling**, see at least the 10 most urgent companies on
   a standard 1440-wide screen.
4. **Without noticing the page is alive** unless something on the page
   warrants their attention — the page should feel still.

These four criteria are the doctrinal acceptance test. They are
verified manually because they measure a perceptual property, not a
functional one.

---

## § 9 — Doctrinal anti-patterns (forbidden)

The following have been rejected by name and must not return:

- Status pills next to company names
- Coloured badge columns
- Tabs across the top of the trace area
- A persistent sidebar
- An idle pulse on every orb
- "Cyberpunk" decorative animations
- Counters or percent-bars in the trace row
- Filter chips along the header
- Any element that moves without a semantic reason
- Auto-refresh that *visually* re-renders when nothing changed

---

## § 10 — Source of truth

- **This document** — the doctrine. Authoritative.
- **`services/vio_overview.py`** — backbone constants, sanitiser,
  urgency formula, stage-state classifier.
- **`ui/vio.html` + `ui/assets/js/vio.js` + `ui/assets/styles/vio.css`** —
  the Level 1 implementation.
- **`tests/test_vio_document_visibility.py`** — the API contract.
- **`tests/test_vio_company_name_sanitiser.py`** — the defensive hygiene
  contract.

If this doctrine and the code drift, the doctrine wins. Update the code.
