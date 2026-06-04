# VIO 2.0 Constitution

**Status:** Binding design law for Visual Intelligence Organism (VIO) work.
**Supersedes:** Dashboard-first, queue-first, card-first operator UI as primary navigation.
**Companion doctrine:** [`VIO_DOCTRINE.md`](./VIO_DOCTRINE.md) — the visual-language and motion charter the Level 1 unified-line build is implemented against. The Constitution defines *what* VIO is; the Doctrine defines *how it must look and behave*.

Design anchors: Carl Visagie hand-drawn sketches (Organism View + per-company Living Timeline). Engineering may improve implementation; engineering may **not** replace the core model.

> **2026-06-04 update — Level 1 redesign shipped.** The first-screen view has been rebuilt as the doctrine-compliant *unified-line* surface: every company is now exactly one continuous SVG trace through the 7-stage backbone (`intake → classification → validation → evidence mapping → review → approval → conversion`), with a single allowed branch for `client follow-up`. Lines are urgency-sorted top-down. Stillness is the default; the only animation in the entire system is the 4-second breathe on `waiting_client`. Level 2 (the per-company immersive landscape) is the explicit next build; a clear placeholder is shown when an operator clicks a line.

---

## The Company Story Doctrine

The primary object of the platform is:

**THE COMPANY STORY**

Not:

- Queue entries
- Intake IDs
- Projects
- Workflow stages
- Tickets
- Tables
- Dashboard cards

Those are implementation details. The Company Story is the first-class citizen.

---

## The Golden Question

Every screen must answer:

> **What is this company's story right now?**

If a screen cannot answer that question, it does not belong in VIO.

---

## Intake Universe Entry

**Click:** INTAKE ORB

The operator immediately enters the **Intake Universe**.

No intermediate pages. No queue screen. No dashboard. No inbox. No card wall.

The first view contains — **all visible immediately:**

- Search
- Recent Company Stories
- Company Orb
- Living Timeline

Each row is **Company Orb + Living Timeline**. Never a table row.

---

## The Company Orb

The Company Orb **owns** the story.

The Company Orb represents:

- Company
- Owner
- Identity
- History
- Relationship

The orb is not the workflow. The orb is the **owner** of the workflow.

---

## The Living Timeline

The timeline **tells** the story.

The timeline communicates:

- Progress
- Health
- Activity
- Waiting
- Completion
- Failure
- Attention required

The timeline is the **primary information carrier**. Not cards. Not tables. Not forms.

### Line thickness (information, not decoration)

| Visual | Meaning |
|--------|---------|
| Thin | Idle |
| Medium | Normal flow |
| Heavy | High activity |
| Broken segment | Issue on the path |
| Waiting segment | Customer action needed |

### Color (semantic)

| Color | Meaning |
|-------|---------|
| Green | Healthy |
| Amber | Waiting |
| Blue | Processing |
| Red | Broken |
| Purple | Learning |

### Visual states

- **Healthy** — green, calm pulse, stable line
- **Active** — blue, gentle motion, flow visible
- **Waiting** — amber, slow pulse
- **Issue** — orange, visible warning marker
- **Critical** — red, fracture effect, immediate priority
- **Completed** — green glow, brief celebration, then calm

Stages appear **only when real events occur**. No placeholder workflow stages. A brand-new customer may show only Company Orb + initial upload folder — nothing more.

---

## Notifications

Notifications **never** create a separate workspace.

Notifications **elevate** a story:

- Story moves to top
- Active segment gains visual priority
- Timeline indicates why attention is required

The operator remains in the same universe.

---

## State Before Detail

The operator should understand **before opening anything:**

- Who
- Where
- Health
- Risk
- Next action

Clicks reveal detail. The default view reveals state.

---

## Progressive Disclosure

1. **Default:** Company Story (orb + timeline + status)
2. **Click:** Stage detail
3. **Click:** Documents (under headings, sections, classifications)
4. **Click:** Document detail / viewer

The operator drills deeper **without losing context**. Documents stay attached to their timeline position — never a separate workflow context.

**Pixar rule:** Build a Pixar movie viewed through a sniper scope — the world is alive, but only what matters is visible until requested.

---

## No Hunting Rule

The operator must **never search for state**. The state must present itself.

If an operator has to inspect multiple panels to determine status, the design has failed.

Within **five seconds**, a first-time operator must know:

- Who is this company?
- Where are they?
- What is healthy?
- What is waiting?
- What is broken?
- What happens next?

Without reading documentation. If that is not true, the design is incomplete.

---

## The Forensic Foundation

The forensic engine remains the **source of truth**.

The timeline is a **visual representation of truth**. The timeline never invents state.

Every segment originates from:

- Intake
- Custody
- Evidence
- Verification
- Delivery
- Recovery
- Integrity proof

No decorative state. No synthetic progress.

Canonical data paths: `services/intake/` pipeline, custody timeline, evidence registry (derived), integrity proof, audit receipts, transaction lifecycle.

---

## Layer Model

### Layer 1 — Organism View

Small number of major platform orbs (Acquisition, Intake, Evidence, Learning, Knowledge, Observability, Alerts). Living status map. Intentionally minimal. Never cluttered. Never a dashboard. Never a collection of cards.

### Layer 2 — Timeline Universe

Click an orb → enter that organ's universe. For Intake: search + recent company stories, each with orb + living timeline, most recent first.

---

## Explicit Rejections

Reject:

- Queue-first design
- Card-first design
- Dashboard-first design
- Widget-first design
- Table-first design
- Notification inboxes as primary workflow
- Multiple competing navigation systems
- Parallel representations of the same truth

Do not build a dashboard. Do not build a workflow tracker. Do not build a CRM. Do not build another compliance application.

Build a **Living Compliance Organism**.

VIO remains the **primary interface**. Existing cockpit panels (COTE, queue cards, Evidence Integrity counts) are operational telemetry — they feed timeline segments; they do not replace VIO as primary navigation.

---

## Success Condition

A first-time operator opens VIO and within five seconds knows who, where, health, waiting, broken, and next — **without reading documentation**.

If that is not true, the design is incomplete.

---

## Implementation Status

| Component | Status |
|-----------|--------|
| VIO 2.0 Intake Universe | **Not built** |
| COTE organism orbs (`cognitive-topology.js`) | Exists — Layer 1 partial, not VIO 2.0 |
| Forensic engine | Built — feeds future timeline segments |
| This constitution | **Binding** for all future VIO work |
