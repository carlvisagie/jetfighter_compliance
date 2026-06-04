# Founding-Beta Rename Plan
*Status: planned. Not blocking production. Tracked separately to prevent shotgun refactors.*

---

## What this is

The `founding_beta` name appears in ~70 files. **Almost all of it is canonical business logic**, not stale residue:

- `services/acquisition/founding_beta_mode.py` — the prey-gate that lowers acquisition thresholds during early discovery.
- `services/intake/mode.py` — the `is_intake_mode()` helper that reads `KYC_FOUNDING_BETA_MODE`.
- `services/intake/`, `services/acquisition/`, `services/durable_storage.py` — call sites that branch on the mode.
- `ui/control.html`, `ui/assets/js/cockpit-intake.js`, etc. — operator UI strings that surface the mode to humans.

The organism's `beta_residue_scan` correctly flags these as **AMBER** — "active source code references the deprecated `founding_beta` name." That is truth, not noise.

## Why it isn't done yet

A previous session looked at this and found:

> structural business logic and is not simply "beta" residue to be purged blindly

Renaming touches:
- 1 Python file rename (`services/acquisition/founding_beta_mode.py`)
- ~15 active services modules with calls / imports
- 4 UI/JS/CSS files with strings the operator sees
- 1 env-var name (`KYC_FOUNDING_BETA_MODE`)
- 1 storage directory name (`data/founding_beta/` — production-data sensitive)
- ~20 test files
- 5 doctrine docs

Total: ~70 files. A single-session refactor with no end-to-end verification of the acquisition pipeline would be exactly the kind of "shotgun fix" that previous agents got burned on.

## Why AMBER is acceptable in the meantime

The organism reports the truth: "15 source files still use the deprecated name." That signal is **honest** — it tells the operator the rename is unfinished. Suppressing the scanner would lie.

The mode itself works correctly. AMBER does not block customer flow, payments, uploads, or revenue.

## The rename, when it happens

### Target name

`expanded_discovery_mode` — describes the actual behavior (expanded prey gate, lowered thresholds, broader signal capture) without invoking time-bound branding.

### Rename map

| Old | New |
|---|---|
| `services/acquisition/founding_beta_mode.py` | `services/acquisition/expanded_discovery_mode.py` |
| `KYC_FOUNDING_BETA_MODE` env var | `KYC_EXPANDED_DISCOVERY_MODE` (with the old name as a deprecation alias for one release) |
| `is_intake_mode()` / `is_founding_beta_mode()` | `is_expanded_discovery_mode()` |
| `passes_founding_beta_prey_gate(...)` | `passes_expanded_discovery_prey_gate(...)` |
| `beta_residue_scan` check | `legacy_mode_naming_scan` check |
| `KYC_FOUNDING_BETA_DOCTRINE.md` | `EXPANDED_DISCOVERY_DOCTRINE.md` |
| UI labels "Founding Beta" / "Beta" | "Expanded Discovery" / "Early Discovery" |
| `data/founding_beta/` directory | **DO NOT RENAME** — production-data path. Read-compatibility shim only. |

### Required steps in the rename PR

1. Add the new env var and function names as aliases of the old ones; keep the old ones working.
2. Migrate call sites to the new names module-by-module, running tests after each module.
3. Move/rename the file once all imports go through aliases.
4. Update UI strings.
5. Add a deprecation warning emitter to the old names; remove after one production deploy cycle.
6. Update doctrine doc; rename the residue check.
7. Run the full pytest suite (target: ≥865 green) and the in-prod authenticated VIO probe (`scripts/probe_vio_overview.py`).
8. Deploy. Verify the organism flips from AMBER to GREEN on the residue check.
9. **DO NOT** rename `data/founding_beta/` — that path is a storage convention with possible historical artifacts. Read-side may dual-read both directories transparently.

### Estimated effort

One focused session, ~2 hours, with the full test suite running between every module migration. **Not** a side-quest to be folded into other work.

---

*This document is read-only to ordinary agents. The single-mandate change above is the only sanctioned path; ad-hoc partial renames are forbidden — they leave the codebase in a worse, half-renamed state.*
