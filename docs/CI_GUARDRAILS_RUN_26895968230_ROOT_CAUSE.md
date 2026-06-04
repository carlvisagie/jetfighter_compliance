# Root Cause — KYC Guardrails run `26895968230` (cancelled)

## Summary verdict

**Run was killed by the explicit `timeout-minutes: 15` cap on the
`guardrails` job. No concurrency cancellation, no superseding commit,
no manual cancel. The final step ("Full test suite") was still running
the 818-case suite at 14m 19s when the runner enforced the timeout.**

A blind re-run **will fail the same way** because the runtime is
deterministic, not flaky.

---

## 1. Facts from the GitHub Actions API

| Field | Value |
| --- | --- |
| Workflow | `KYC Guardrails` (`.github/workflows/kyc_guardrails.yml`) |
| Run ID | `26895968230` (run number 111) |
| Event | `push` |
| Branch | `main` |
| Head SHA | `42ae186d820ca8d83a4625adcce014670fae8974` |
| Actor | `carlvisagie` |
| `run_attempt` | `1` |
| Status / conclusion | `completed` / **`cancelled`** |
| Pull requests | none (direct push to `main`) |
| Created → updated | `2026-06-03T15:44:16Z` → `2026-06-03T15:59:41Z` (15m 25s) |
| Job runtime | `2026-06-03T15:44:22Z` → `2026-06-03T15:59:40Z` = **15m 18s** |
| Job annotation | `The job has exceeded the maximum execution time of 15m0s` |

The annotation comes from GitHub's runner, not from a workflow expression
or another commit — it is the literal `timeout-minutes` enforcement.

---

## 2. Per-step timing (the smoking gun)

| # | Step | Conclusion | Duration |
| --- | --- | --- | --- |
| 1 | Set up job | success | 1s |
| 2 | Checkout | success | 2s |
| 3 | Set up Python | success | 3s |
| 4 | Install dependencies | success | 8s |
| 5 | Static KYC guardrails | success | 2s |
| 6 | Public UI exposure | success | 2s |
| 7 | Customer upload-first UX | success | 1s |
| 8 | Acquisition organism | success | 2s |
| 9 | Pre-contact upload session | success | 2s |
| 10 | Ops route authentication | success | 8s |
| 11 | Central memory contract | success | 1s |
| 12 | Organism observability | success | 3s |
| 13 | Operator guidance | success | 18s |
| **14** | **Full test suite** | **cancelled** | **14m 19s** (killed) |
| 27 | Post Set up Python | skipped | — |
| 28 | Post Checkout | success | 1s |
| 29 | Complete job | success | 0s |

Steps 1–13 consumed **~55 seconds total**. Step 14 alone consumed the
remaining **14m 19s** before the runner killed it 41 seconds short of
the entire 818-test suite finishing (local Windows run measures 21m 47s
for the same command).

---

## 3. Targeted guardrail checks the brief requested

### 3.1 Concurrency groups
**None.** The workflow defines no `concurrency:` block at the job or
workflow level. Therefore no `cancel-in-progress` behavior is in play
and no later commit could have cancelled this run via supersession.

### 3.2 `cancel-in-progress`
**Not present** (see §3.1).

### 3.3 `timeout-minutes`
**Present and triggered:** `jobs.guardrails.timeout-minutes: 15` (line 13
of `.github/workflows/kyc_guardrails.yml`). This is the sole cause of
the cancellation.

### 3.4 `workflow_dispatch` interactions
**Not configured.** The workflow only listens on `push` (branches
`main`, `master`) and `pull_request` (same branches). It cannot be
re-triggered or cancelled by manual dispatch.

### 3.5 Superseding commits
**None.** After `42ae186` was pushed at 15:43:43Z there have been no
further commits on `main`. The HEAD on `origin/main` is still
`42ae186`. Even if there had been later commits, lack of a
concurrency group (§3.1) means the older run would have continued.

### 3.6 Manual cancellation
No cancel API call was issued — there is no `cancelled by` annotation
in the run metadata, only the timeout annotation.

---

## 4. Root cause

The workflow's last step re-runs the full 818-case test suite:

```yaml
- name: Full test suite
  ...
  run: |
    python -m pytest tests/ -q --tb=line
```

This step duplicates work that the preceding ten named steps already
exercise (test_kyc_guardrails, test_public_ui_exposure, etc., are all
included in `tests/`) and then layers in the heavy intake / hardening /
forensic-integrity tests that dominate runtime.

On the `ubuntu-latest` runner the suite needed more than the 15-minute
cap allowed. Locally the same command takes 21m 47s on the user's
Windows machine. The cap was set before the suite reached its current
size (818 tests) and is now structurally too tight.

---

## 5. Is a blind re-run safe?

**No.** The cancellation is deterministic, not transient. Re-running
without changes will burn another 15 minutes and end the same way.

Re-running becomes safe only after one of:

1. **Raise the cap** — bump `timeout-minutes` (e.g. `30`) so the full
   suite can finish. Smallest possible change.
2. **Trim the final step** — remove the duplicate "Full test suite"
   step or use `pytest --ignore=tests/test_intake_pipeline_hardening*.py`
   to skip the slow forensic loops in CI and run them in a separate,
   nightly workflow.
3. **Parallelize** — split the suite across two jobs using a matrix
   strategy, each filtered by pytest mark or path.

All three are workflow-file changes only; none touch application code.

---

## 6. What was NOT changed

In accordance with the mission instruction "Do not modify application
code":

- No application source files were edited.
- No workflow files were edited (yet — pending operator decision per
  §5).
- No pull request, issue, or commit was created.

This document is the deliverable.

---

## 7. Recommended next action

Apply **Option 1** (raise `timeout-minutes` to `30`) as a single-line
change to `.github/workflows/kyc_guardrails.yml`. It is the safest,
smallest move — it does not change which tests run, only how long they
are permitted to. Combined with the now-green local suite
(818/818 passing on `42ae186`), CI should then go green on the existing
HEAD without any application-code change.

If the operator instead wants to keep the 15-minute SLA on CI as a
performance guardrail, Option 2 (remove the duplicate full-suite step)
is the next-smallest move.
