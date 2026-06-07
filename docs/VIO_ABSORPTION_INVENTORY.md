# VIO Absorption Inventory

> **Principle (Carl, 2026-06-04):** "Only one door into VIO — Upload.
> Everything client/company belongs inside VIO. Everything else is
> organism infrastructure that surfaces on the constellation."
>
> **Discipline (Carl, 2026-06-04):** "The 14-ish surfaces in the brief
> are a kill-list, not a co-exist list. Migration order is: prove the
> capability inside VIO → delete the old surface in the same commit."

This file is the migration map. Every existing operator surface is
either (a) folded into VIO L1/L2/side-panel frames, (b) folded into the
constellation as an organism orb/glyph, or (c) explicitly out of scope
(public-facing customer surfaces, dev tools).

Status legend:

| Status        | Meaning |
| ------------- | ------- |
| `OPEN`        | Old surface still live, VIO equivalent not yet built |
| `IN VIO`      | Capability shipped inside VIO but old surface still live (transitional) |
| `KILLED`      | Old surface deleted; VIO is the only path |
| `NOT SCOPED`  | Public/customer surface or dev tool; never absorbed |

---

## § 1 — The kill-list (Carl's brief, §4)

The 15 surfaces named in `docs/history/VIO_SOURCE_BRIEF.md` §4. Each must be
either absorbed into VIO or deliberately killed. Listed in the order
they will be migrated (most operationally critical first).

| # | Old surface                       | VIO destination                              | Migration target                                            | Status |
| - | --------------------------------- | -------------------------------------------- | ----------------------------------------------------------- | ------ |
| 1 | Intake Queue                       | L1 (every active intake = one trace)         | Trace urgency-sort + waiting badge already shipped          | IN VIO |
| 2 | Upload pipeline                    | Constellation `Upload` orb → L1               | Upload orb is the SOLE door to VIO                          | OPEN   |
| 3 | Evidence Integrity                 | L2 side-panel frame (per-intake)             | Existing `eiFrame()` + reprocess button                     | IN VIO |
| 4 | Payment / PayPal actions           | L2 spine `payment` branch + side-panel frame | Side-panel frame exists; auto-confirm on webhook            | IN VIO |
| 5 | Operational Command                | Constellation `Command` glyph + L2 actions   | System-wide actions land on constellation; per-intake on L2 | OPEN   |
| 6 | Operational Intelligence           | Constellation `Intelligence` glyph           | KPI tiles + alert stream                                    | OPEN   |
| 7 | Onboarding Intelligence            | L1 + L2 onboarding cluster                   | Onboarding state surfaces as an above-spine cluster         | OPEN   |
| 8 | Acquisition Intelligence / Reddit  | Constellation `Acquisition` orb              | Lead discovery + Reddit approval queue                      | OPEN   |
| 9 | Operational Alerts                 | Constellation alerts ribbon + per-trace flag | Alerts ride above the L1 trace strip                        | OPEN   |
| 10| Compliance Intelligence Watch      | Constellation `Compliance` orb               | New-rule feed + domain reclassification triggers            | OPEN   |
| 11| Project Command Strip              | L2 `project` branch + side-panel frame       | Per-intake project state on the spine                       | IN VIO |
| 12| Knowledge / Advice (Cockpit)        | Constellation `Knowledge` orb                | Contextual mentor + concept overlay                          | OPEN   |
| 13| Organism Health                    | Constellation `Health` orb + env-ribbon      | Memory integrity, scheduler, transport, etc.                | OPEN   |
| 14| Engine Integration                 | Constellation `Engine` glyph                 | Scheduler heartbeat + ingest pulse                          | OPEN   |
| 15| Control / Operator Cockpit         | DECOMPOSED into the above                    | Killed entirely after all 14 items above migrate            | OPEN   |

**Killing Control (#15)** is the terminal step. Until items 1–14 are
either `IN VIO` or `KILLED`, Control stays alive as a fallback. Once
item 14 lands, the same commit that ships it MUST also delete
`ui/control.html` and any operator-facing route that points to it.

---

## § 2 — Every operator HTML, classified

Complete inventory of `ui/*.html` as of 2026-06-05. The "fold into"
column names exactly where each capability lives after migration.

| File                       | What it is today                                       | Category    | Fold into                                  | Status      |
| -------------------------- | ------------------------------------------------------ | ----------- | ------------------------------------------ | ----------- |
| `control.html`             | The big one — operator cockpit, 14 panels             | Operator    | Decomposed across L1 / L2 / constellation  | OPEN        |
| `command.html`             | Command Center (operational actions)                  | Operator    | Constellation `Command` glyph              | OPEN        |
| `memory.html`              | Central organism intelligence viewer                  | Operator    | Constellation `Memory` orb                 | OPEN        |
| `inbox.html`               | Order inbox (delivered projects)                      | Operator    | L1 trace for archived intakes              | OPEN        |
| `status.html`              | Per-project status                                    | Operator    | L2 side-panel frame                        | OPEN        |
| `event.html`               | Chain-of-custody event detail                         | Operator    | L2 custody frame (already exists)          | IN VIO      |
| `scan.html`                | Evidence scan & log                                   | Operator    | L2 papers cluster + scan input             | OPEN        |
| `knowledge.html`           | Operator knowledge cockpit                            | Operator    | Constellation `Knowledge` orb              | OPEN        |
| `lead_discovery.html`      | Acquisition pipeline                                  | Operator    | Constellation `Acquisition` orb            | OPEN        |
| `onboarding_validation.html` | MVP onboarding segments                              | Operator    | L2 onboarding cluster                      | OPEN        |
| `new_client.html`          | Operator-initiated new client                         | Operator    | L2 (creates a new trace)                   | OPEN        |
| `vendor_quote.html`        | Send vendor quote                                     | Operator    | L2 vendor branch + side-panel frame        | OPEN        |
| `healthz.html`             | Platform health check                                 | Operator    | Constellation `Health` orb                 | OPEN        |
| `webhook_test.html`        | Dev tool: test kickoff()                              | Dev         | Stay as-is                                 | NOT SCOPED  |
| `vio.html`                 | VIO itself                                            | Operator    | THIS IS THE DESTINATION                    | DESTINATION |
| `index.html`               | Public landing                                        | Customer    | Stay as-is                                 | NOT SCOPED  |
| `intake.html`              | Public intake form                                    | Customer    | Stay as-is                                 | NOT SCOPED  |
| `inquiry.html`             | Public inquiry / upload                               | Customer    | Stay as-is                                 | NOT SCOPED  |
| `upload.html`              | Public upload                                         | Customer    | Stay as-is                                 | NOT SCOPED  |
| `shop.html`                | Public compliance services storefront                 | Customer    | Stay as-is                                 | NOT SCOPED  |
| `continue.html`            | Customer continuation flow                            | Customer    | Stay as-is                                 | NOT SCOPED  |
| `login.html`               | Operator sign-in                                      | Auth        | Stay as-is                                 | NOT SCOPED  |

---

## § 3 — Control panel decomposition

`ui/control.html` is 97 KB and contains 14 distinct panels. This table
shows where each panel lands after the migration. When the last panel
ships in its new home, `control.html` itself is deleted.

| Panel inside control.html         | Lands in                                          | Status  |
| --------------------------------- | ------------------------------------------------- | ------- |
| Operator cockpit (header)         | Constellation header strip                        | OPEN    |
| Evidence Integrity                | L2 side-panel frame (eiFrame)                      | IN VIO  |
| Operational organism (state strip) | Constellation `Organism Health` orb               | OPEN    |
| Intake Queue                      | L1 trace strip                                    | IN VIO  |
| Operational command               | Constellation `Command` glyph + L2 actions        | OPEN    |
| Operational intelligence          | Constellation `Intelligence` glyph                | OPEN    |
| Onboarding & upload experience    | Constellation `Onboarding` orb / L1 onboarding   | OPEN    |
| Upload analysis                   | Constellation `Upload` orb (already vio-bound)    | IN VIO  |
| Acquisition Intelligence          | Constellation `Acquisition` orb                   | OPEN    |
| Reddit — Approve or Deny          | Constellation `Acquisition` orb child surface     | OPEN    |
| Operational Alerts                | Constellation alerts ribbon                        | OPEN    |
| Compliance Intelligence Watch     | Constellation `Compliance` orb                    | OPEN    |
| Project command strip             | L2 `project` branch + side-panel frame             | IN VIO  |
| Workflow knowledge (per phase)    | L2 stage-anchor frame (per stage clicked)         | IN VIO  |
| Organism health (10 cards)        | Constellation `Health` orb                        | OPEN    |
| Operational actions               | Constellation actions glyph + L2 per-intake       | OPEN    |
| Registry (recent projects)        | L1 trace list (already shows this)                | IN VIO  |
| Contextual mentor (CKO)            | Constellation `Knowledge` orb                     | OPEN    |

---

## § 4 — Migration discipline

For every absorption:

1. **Build the VIO destination first.** The capability must be
   reachable, usable, and at parity (or better) inside VIO. Operator
   acceptance test: can the same task be performed from VIO alone?

2. **Prove it works in production.** Open the live VIO, perform the
   task, screenshot the result. Confirm no regression on the old
   surface in the same session.

3. **Delete the old surface in the same commit.** No co-existence
   period. The old route returns `404` or redirects to VIO. The HTML
   file is removed from `ui/`. Tests that referenced it are deleted or
   migrated.

4. **Update this inventory.** Mark the migrated surface `KILLED` with
   the commit SHA and date.

If the third step is skipped, the kill-list becomes a co-exist list,
and VIO regresses into another tab among many. Carl 2026-06-04: that
is the failure mode this discipline exists to prevent.

---

## § 5 — Public/customer surfaces (out of scope)

These are NEVER absorbed into VIO. They are the customer's front door,
not the operator's working surface.

- `index.html` — public landing
- `intake.html` — public intake form
- `inquiry.html` — public inquiry / upload
- `upload.html` — public upload
- `shop.html` — public storefront
- `continue.html` — customer continuation
- `login.html` — operator/customer sign-in

Any change to these surfaces is scoped independently and must NOT
introduce dependencies on VIO components.

---

## § 6 — Source of truth

- This inventory is the migration map. Updated on every kill commit.
- The doctrine that drives it lives in:
  - `docs/VIO_DOCTRINE.md` (visual cognition law)
  - `docs/VIO_CONSTITUTION.md` (boundary law)
  - `docs/history/VIO_SOURCE_BRIEF.md` (Carl's brief + kill list)
  - `docs/KYC_ORGANISM_DOCTRINE.md` (Autonomy by default)
