# PRODUCTION IS THE ONLY TRUTH
*Status: binding. Adopted 2026-06-04 after the "40-intakes" forensic incident.*
*Enforcement: runtime envelopes + CI guardrail tests + UI ribbon. Violations fail the build.*

---

## The single rule

**There is one environment: PRODUCTION.**

| Truth | Lives here | Reachable how |
|---|---|---|
| All customer data | Render disk `kyc-data` mounted at `/var/data` | only via `https://compliance.keepyourcontracts.com` |
| All organism state | same disk, `data/memory/` under `/var/data` | operator API with `OPS_API_KEY` or session |
| All counts ever quoted to a human | same disk | the operator API responses, never the local filesystem |

Anything that is not production is **non-production noise**. Tests run in throwaway temp dirs and their output is invisible to every human and every agent. The local `data/` directory on a developer machine is **never** a source of truth — it is at best a scratch pad that may contain anything (test pollution, dead fixtures, abandoned experiments). It must never be cited.

---

## Why this exists

On 2026-06-04 the platform was reported to have **40 intakes / 40 uploads / 605 projects**. The forensic audit proved those numbers came from `E:\JetFighter_Compliance\data\` on one developer machine, polluted by pytest runs. Production (`/var/data`) had `0 / 0 / 0` — correctly, because no customer had ever uploaded. Hours were lost while agents quoted local junk as if it were customer reality.

The failure was structural: nothing in the system distinguished a production count from a non-production count when reporting to a human. This document, and the guardrails it requires, eliminate that.

---

## What every operator response MUST carry

Every operator-protected API endpoint returns a payload that includes:

```json
{
  "_env": {
    "environment": "production" | "non-production",
    "data_root":   "/var/data" | "<some temp or local path>",
    "host":        "kyc-backend",
    "server_time_utc": "2026-06-04T07:34:12Z",
    "git_commit":  "aec9c45",
    "trust":       "trusted" | "DO_NOT_TRUST"
  },
  ... actual payload ...
}
```

- `environment: production` → `trust: trusted`. The count is real.
- Anything else → `trust: DO_NOT_TRUST`. The count is noise.

The classifier is brutally simple — *any* of these makes it non-production:
- `ENVIRONMENT` env var is not exactly `"production"`
- `data_root` does not resolve under `/var/data`
- `OPS_API_KEY` is not configured (a real production deploy always has it)

There is no "test" environment, no "staging", no "preview". The contract recognises two states only: **production** and **noise**.

---

## What every operator UI MUST display

`ui/vio.html`, `ui/control.html`, and any other operator surface render an environment ribbon across the top sourced from `GET /api/operator/environment-label`:

- **PRODUCTION** — small, calm, dark-green strip. Doctrine §5 of the VIO charter applies (stillness is the baseline).
- **NON-PRODUCTION** — large, deep-red strip across the full width with bold white text: `⚠ NON-PRODUCTION DATA — DO NOT TRUST ANY COUNT ON THIS PAGE`. The ribbon dims the rest of the UI to 50% opacity until acknowledged so no count can be screenshotted without the warning.

If the ribbon endpoint fails to respond, the page treats it as **non-production** and shows the warning. There is no benefit-of-the-doubt.

---

## What every agent (human or AI) MUST do before quoting a count

1. Hit `GET /api/operator/<endpoint>` against `https://compliance.keepyourcontracts.com` with `X-Ops-Key: $OPS_API_KEY`.
2. Read the response.
3. Cite the count **with** the `_env.environment`, `_env.data_root`, and `_env.server_time_utc`.

Correct:
> "Production reports 0 intakes (env=`production`, data_root=`/var/data`, t=`2026-06-04T07:34Z`)."

Forbidden:
> "We have 40 intakes." ← no provenance — caller is lying or guessing.

> "Local has 40 intakes." ← local is never a count that matters.

> "Looking at `data/intakes/`…" ← reading the local filesystem to answer "how many intakes do we have" is grounds for distrust. Hit production.

This rule is the **first** thing in `AGENTS.md`. Violation is a process bug.

---

## What pytest MUST do

`tests/conftest.py` ships an autouse session fixture that:

1. Sets `KYC_DATA` to a per-session `tmp_path` **before** any `services.config` import.
2. Patches `services.config.DATA` and `services.config.PROJECTS` to the same tmp_path.
3. Patches the ledger path so test events do not append to the real `data/ledger/ledger.log`.
4. Snapshots `data/intakes/`, `data/projects/`, `data/founding_beta/`, and `data/ledger/` mtimes at session start.
5. Asserts at session end that none of those mtimes changed. A test that mutates the canonical `data/` directory fails the session loudly.

Enforced by `tests/test_pytest_data_isolation_guardrail.py`.

---

## What scripts MUST do

Every script that touches paperwork (any script that creates, reads, modifies, or counts intakes/projects/uploads) hits production HTTPS with the operator key. There is no `--target=local` mode. The local `data/` directory is not a target.

The single sanctioned helper:

```python
from scripts._prod_only import production_client
client = production_client()             # exits 2 if OPS_API_KEY missing
counts = client.organism_counts()        # always production
```

`production_client()` hard-codes the production base URL, requires `OPS_API_KEY`, and refuses to be redirected. Scripts that want to "test against local" do not exist; write a pytest instead.

Enforced by `tests/test_scripts_hit_production_guardrail.py`.

---

## What the local `data/` directory is for

Nothing operator-facing. It exists because the codebase imports paths from `services.config` and those paths point at `data/` when `KYC_DATA` is unset locally. It accumulates pytest junk and the occasional manual experiment. It is **not** authoritative, **not** monitored, **not** quoted.

A future agent that wants to query "how many companies are there" must hit production. A future agent that wants to run `ls data/intakes` and report back what it sees is **breaking the contract**.

---

## Enforcement matrix

| Failure mode | Caught by |
|---|---|
| Operator endpoint returns payload without `_env` | `tests/test_environment_envelope_guardrail.py` |
| Operator endpoint returns `environment != production` and caller is on production base URL | runtime ribbon + the same test |
| Operator UI lacks ribbon | `tests/test_environment_envelope_guardrail.py` + visual review |
| Script writes to / reads from local `data/` for paperwork answers | `tests/test_scripts_hit_production_guardrail.py` |
| Pytest writes to canonical `data/` | `tests/conftest.py` autouse + `tests/test_pytest_data_isolation_guardrail.py` |
| Agent quotes count without environment attribution | `AGENTS.md` + this document (process, not CI-enforceable) |

---

## When this contract changes

This document is **read-only** to ordinary agents. Modifications require an owner-approved PR that updates the enforcement matrix in the same commit. The single rule at the top — *Production is the only truth* — does not change.
