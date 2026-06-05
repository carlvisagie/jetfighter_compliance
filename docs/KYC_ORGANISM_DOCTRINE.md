# KYC Organism Doctrine

## What KYC is

KYC is **not** compliance software. KYC is an **adaptive operational burden-relief organism**.

The platform exists to:

- Reduce operational overwhelm
- Absorb compliance complexity
- Organize chaos
- Build trust
- Guide intelligently
- Learn continuously
- Surface contextual intelligence at the right moment

## Autonomy by default

> "Anything that can be autonomous, must be." — operator directive, 2026-06-05.

Every step in the organism that does not strictly require human judgment
runs itself. The operator's surface (VIO) exists to expose **only** what
the organism cannot autonomously resolve. If a task can be detected,
chosen, retried, repaired, escalated, or completed without human input,
it does so silently and writes the outcome to central memory + the
custody chain.

The decision test, applied to every new feature, capability, or button:

1. Can the organism do this without operator input? → it must.
2. Does this require operator judgment? → surface it on VIO, with the
   smallest visual footprint that conveys the demand.
3. Can the demand be partially auto-resolved (e.g. auto-draft a reply,
   auto-fill a generated doc, auto-retry an OCR pass)? → do the part
   the organism can do, surface only the remainder.

Concrete consequences:

- **Reprocess EI** runs autonomously when staleness signals fire (new
  doc uploaded, OCR became available, domain reclassified). The manual
  "reprocess" button is an override, not the default path.
- **Domain detection**, **gap detection**, **OCR fallback**,
  **classification**, **deduplication**, **custody capture** — all
  autonomous. The operator does not orchestrate them.
- **Findings of severity ≥ high**, **confirmation_needed fields**, and
  **payment confirmation** require human judgment and are the *only*
  things that should ever ask for attention on VIO.

Surfacing operator attention is expensive. Use it sparingly, never for
work the organism can do itself.

## Standalone platform

Production runs from **one repository and runtime**. Legacy desktop encyclopedia folders are **import sources only** — never runtime dependencies.

Canonical knowledge: `data/knowledge_cockpit/`  
Canonical memory: `data/memory/`  
Operator surface: `ui/control.html` with **Contextual Knowledge Overlay**

## One organism

| Layer | Role |
|-------|------|
| Runtime | FastAPI + deployable platform |
| Cockpit | Mission control for solo operator |
| Central memory | Canonical timeline and learning |
| Acquisition organism | Find real operational burden |
| Compliance organism | Watch authoritative sources |
| Knowledge organism | Contextual mentor + explainer |
| Telemetry | Nervous system signals |

No duplicated encyclopedia systems. No parallel brains.

## Acquisition doctrine

Hunt **operational burden**, not topic chatter:

- Confusion, pressure, financial stress, questionnaire burden
- Quiet overwhelm and documentation gaps

Build trust first. Help first. Teach first. Upload-first only after trust.

## Upload-first doctrine

**Customer:** upload what you have.  
**Organism:** classify, organize, explain, guide, reduce overwhelm, surface gaps.

Customers should not self-diagnose compliance frameworks.

## Knowledge cockpit doctrine

The Knowledge Cockpit is:

- Contextual mentor (overlay on what you are viewing)
- Operational explainer in plain language
- Memory augmentation via central memory
- Acquisition, compliance, and evidence interpretation assistant

It is **not** a passive encyclopedia or a separate app.

## Operational language

Explain like aviation maintenance, inspection readiness, evidence discipline, chain of custody — not consultant jargon.

## Evolution

The organism improves daily from telemetry, operator approvals, uploads, acquisition outcomes, and recurring confusion patterns — all written to central memory.
