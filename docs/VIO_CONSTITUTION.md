# VIO 2.0 Constitution

**Status:** Binding design law for Visual Intelligence Organism (VIO) work.
**Supersedes:** Dashboard-first, queue-first, card-first operator UI as primary navigation.
**Companion doctrine:** [`VIO_DOCTRINE.md`](./VIO_DOCTRINE.md) — the visual-language and motion charter the Level 1 unified-line build is implemented against. The Constitution defines *what* VIO is; the Doctrine defines *how it must look and behave*.

Design anchors: Carl Visagie hand-drawn sketches (Organism View + per-company Living Timeline). Engineering may improve implementation; engineering may **not** replace the core model.

> **2026-06-04 update — Level 1 + Level 2 both shipped.** The first-screen view has been rebuilt as the doctrine-compliant *unified-line* surface: every company is now exactly one continuous SVG trace through the 7-stage backbone (`intake → classification → validation → evidence mapping → review → approval → conversion`), with a single allowed branch for `client follow-up`. Lines are urgency-sorted top-down. Clicking any line takes the operator into the **Level 2 immersive landscape** — a full-screen horizontal canvas where the same spine extends into perpendicular branches that sprout only where real complexity warrants it (uploaded papers, gaps, findings, identifiers, payment, project, generated paperwork). Every visual atom is clickable, opening a recursive side panel with the full per-leaf detail. Stillness is the default at both levels; the only animation in the entire system is the 4-second breathe on `waiting_client`.

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

## The Boundary — VIO Absorbs Everything

**Locked rule** (Carl Visagie, 2026-06-04, amended after the
[`history/VIO_SOURCE_BRIEF.md`](./history/VIO_SOURCE_BRIEF.md) was enshrined):

> **VIO is the only primary operator interface.**
> No separate Control, Command, Status, Inbox, Intelligence,
> Onboarding, or Operational pages as the primary workflow.

VIO contains BOTH universes:

1. **Client / company state** — every active client, their intake,
   evidence, gaps, custody chain, operator-pending actions, alerts
   about *them*, communications, payment state, delivery binder,
   knowledge needed about *this* client. Rendered as **company spines**
   (the sketch).
2. **Organism / subsystem state** — telemetry health, learning state,
   acquisition pipeline, observability, scheduler heartbeat, storage
   durability, payment aging, integrity-proof status, knowledge base,
   alerts about the system itself. Rendered as **organism glyphs**
   inside the VIO canvas.

There are no separate `/ui/control.html`, `/ui/command.html`,
`/ui/inbox.html`, `/ui/intelligence.html`, `/ui/healthz.html` etc.
as **primary** operator surfaces. The kill-list is in
[`history/VIO_SOURCE_BRIEF.md` §4](./history/VIO_SOURCE_BRIEF.md) — 14 surfaces by name.

**Decision test for any new capability:**

| Question | Answer | Where it goes |
|---|---|---|
| Is it about a specific client/company? | yes | Inside VIO as a node, branch, or shape on that company's spine. |
| Is it about the system watching itself? | yes | Inside VIO as an organism glyph (in-place, not a separate page). |
| Could it be on a Control, Command, Inbox, Intelligence, or Operational page? | yes (today) | That page is on the kill-list. Build the capability in VIO and delete the old page in the same commit. |

A capability built into a non-VIO primary surface is a doctrine
violation. **Migrate or delete** — there is no "and also" path.

The **Intake/Upload glyph** is the door into the *company-spine
universe*. Organism glyphs surface their organ's state without taking
the operator off the VIO canvas.

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
