# Archived Files Inventory

**Patch:** 11 — Production Fortress  
**Date:** 2026-06-07  
**Location:** [`../archive/dev_tools/`](../archive/dev_tools/)  
**Policy:** Archive only — **never delete** customer or production truth.

One-off developer diagnostics moved out of repository root to reduce noise and agent confusion. Production scripts remain under `scripts/`.

---

## Archived from repository root

### `.check*` (live/deploy probes)

| File | Former purpose |
|------|----------------|
| `.check_vio_overview.py` | VIO overview smoke |
| `.check_live_css.py` | Live CSS inspection |
| `.check_live_js.py` | Live JS inspection |
| `.check_live_boot.py` | Boot status probe |
| `.check_inline_boot.py` | Inline boot script check |
| `.check_companies.py` | Company list probe |
| `.check_build.py` | Build info check |
| `.check_live_vio_l2.py` | VIO L2 live check |

### `.probe*` (diagnostic probes)

| File | Former purpose |
|------|----------------|
| `.probe_vio.py` | VIO probe |
| `.probe.py` | Generic probe |
| `.probe_company.py` | Company detail probe |
| `.probe_vio2.py` | VIO alternate probe |

### `run_audit*` (patch audit runners)

| File | Former purpose |
|------|----------------|
| `run_audit_patch6.py` | Patch 6 audit |
| `run_audit_patch7.py` | Patch 7 audit |
| `run_audit_patch8d.py` | Patch 8d audit |
| `run_audit_patch8e.py` | Patch 8e audit |

### Corpus / OCR one-offs

| File | Former purpose |
|------|----------------|
| `run_real_corpus_execution.py` | Corpus execution |
| `run_company_20_ocr.py` | OCR batch experiment |
| `run_corpus_execution_harness.py` | Corpus harness |

### `.git_commit_msg*` (ephemeral commit message drafts)

| File |
|------|
| `.git_commit_msg.txt` |
| `.git_commit_msg2.txt` |
| `.git_commit_msg3.txt` |
| `.git_commit_msg_patch2.txt` |
| `.git_commit_msg_patch3.txt` |
| `.git_commit_msg_patch4.txt` |

### Other root one-off diagnostics

| File | Former purpose |
|------|----------------|
| `.count_l2.py` | L2 count script |
| `.final_check.py` | Ad-hoc final check |
| `.repro_sweep.py` | Repro sweep |
| `.diag_vio_dark.py` | VIO dark mode diag |
| `.intake_ei_probe.py` | Intake/EI probe |
| `.poll_overlay_fix.py` | Deploy poll |
| `.verify_live.py` | Live verify |
| `.wait_deploy.py` | Deploy wait |
| `.deploy_probe.py` | Deploy probe |
| `.ei_freshness_probe.py` | EI freshness probe |
| `.scan_ui.py` | UI scan |
| `.poll_sketch_deploy.py` | Sketch deploy poll |
| `.poll_deploy.py` | Deploy poll |
| `.poll_boot_deploy.py` | Boot deploy poll |
| `.git_commit_helper.py` | Commit helper |
| `.css_tail.py` | CSS utility |
| `.copy_sketch.py` | Sketch copy |
| `.unzip_brief.py` | Brief unzip |
| `.live-vio-level2.js` | Live L2 snapshot |
| `.live-vio.js` | Live VIO snapshot |
| `.live-organism-intel.js` | Live organism snapshot |
| `.live-env-ribbon.js` | Env ribbon snapshot |
| `.vio-level2-prev.js` | Previous L2 JS |
| `.boot-extracted.js` | Extracted boot JS |
| `.test_axis.js` | Axis test JS |

---

## Moved to `docs/history/`

| File | Reason |
|------|--------|
| `docs/VIO_SOURCE_BRIEF.md` → `docs/history/VIO_SOURCE_BRIEF.md` | Historical brief; contains reserved-word context allowed in `docs/history/` |

---

## Still canonical (not archived)

- `scripts/` — production verification (`probe_boot_status.py`, `prove_disk_persistence.py`, `repair_intake_integrity_patch10c.py`, …)
- `scripts/audit_reserved_words.py` — Patch 11 governance scanner (new)

---

*Add rows here when future dev tools are archived — one inventory, one location.*
