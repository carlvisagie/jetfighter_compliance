# Organism Core — Extraction to Standalone Repo

**Status:** Planning. No code moves yet.
**Author guarantees:** KYC keeps working at every step. Every dependency is pinned. No floating versions.

---

## 1. Target repo name

**`organism-core`** (kebab-case, GitHub convention)

- URL: `https://github.com/carlvisagie/organism-core`
- Visibility: **Private** (until interfaces are frozen at 1.0.0)
- Branch model: `main` is always release-quality; feature work in short-lived branches
- License: pick once — `MIT` recommended for low-friction internal reuse

---

## 2. Package name

**`organism_core`** (snake_case, Python convention)

- Installed via: `pip install organism-core` (PyPI name) or `pip install git+https://github.com/carlvisagie/organism-core.git@v0.1.0` (git tag)
- Imported as: `from organism_core import AwarenessEngine, Check, ...`
- Distribution build: standard `pyproject.toml` with `setuptools` or `hatchling`

---

## 3. Public interfaces (the frozen contract)

These are the only symbols any downstream product (KYC, Purposeful, Sage, etc.) is allowed to import. Everything else is private and may change between releases.

### 3.1 Importable from top-level package

```python
from organism_core import (
    # Composition root
    AwarenessEngine,

    # Signal collection
    SignalCollector,
    SignalBundle,

    # Checks
    Check,
    CheckResult,

    # Health derivation
    HealthState,
    Severity,
    derive_health,

    # Residue scanning
    Pattern,
    LocationRule,
    ResidueScanner,
    ResidueReport,

    # Recommendations
    RecommendationRegistry,

    # Persistence
    write_snapshot,
)
```

### 3.2 Snapshot contract (the data shape every product produces)

```jsonc
{
  "ok": true,
  "organism": "<product_name>",
  "timestamp_utc": "<ISO-8601 Z>",
  "health_state": "GREEN" | "AMBER" | "RED",
  "current_bottleneck": "<check_name or 'none'>",
  "next_recommended_action": "<string>",
  "visibility_mismatches": ["<check_name>", ...],
  "checks":   [ { "name", "ok", "severity", "detail", "evidence" }, ... ],
  "signals":  { "<collector_name>": { ... }, ... },
  "metadata": { ... },
  "residue":  { ... }      // optional, present only if a scanner is registered
}
```

This shape is part of the public contract. A change to any required field requires a MAJOR version bump.

### 3.3 What is NOT public (private internals)

| Symbol | Reason private |
|---|---|
| `organism_core.awareness.engine._GatingConfig` | implementation detail |
| `organism_core.health.derivation.HealthVerdict` (currently exposed) | consider promoting to public in 0.2.0 |
| Anything not listed in `organism_core/__init__.py.__all__` | not part of the API |

A `__all__` list in `organism_core/__init__.py` is the single source of truth.

---

## 4. Versioning strategy

### 4.1 Semantic versioning, strict

```
MAJOR.MINOR.PATCH

MAJOR = breaking change to any public symbol or snapshot field
MINOR = backwards-compatible additions (new optional fields, new helpers)
PATCH = bug fixes only (no API surface change)
```

### 4.2 Initial release plan

| Version | Meaning | When |
|---|---|---|
| `0.1.0` | First extraction. Same surface as the current vendored copy in KYC. | When repo is created. |
| `0.1.x` | Bug fixes only. KYC stays on `0.1.0` until ready. | As needed. |
| `0.2.0` | First additive change (e.g. promote `HealthVerdict` to public). | When second product (Purposeful) is integrated. |
| `1.0.0` | Public surface frozen. No breaking changes permitted on `1.x` line. | When two or more products have shipped with stable use. |

### 4.3 Hard pinning rules (downstream products)

**Every downstream `requirements.txt` MUST pin exactly:**

```text
# CORRECT — pin to exact version
organism-core==0.1.0

# CORRECT — pin to exact git tag
organism-core @ git+https://github.com/carlvisagie/organism-core.git@v0.1.0
```

**NEVER use floating ranges:**

```text
# WRONG — would auto-upgrade
organism-core>=0.1.0
organism-core~=0.1
organism-core^0.1.0
organism-core @ git+https://github.com/carlvisagie/organism-core.git@main
```

### 4.4 Lockfiles

- KYC checks in `requirements.txt` (already exists) with `organism-core==X.Y.Z`
- If KYC adopts `uv` or `pip-tools` later, also commit the lockfile
- The lock is the source of truth for production deploys; `requirements.txt` is the source of truth for the abstract pin

### 4.5 Tag discipline

- Every release is a git tag in `organism-core`: `v0.1.0`, `v0.1.1`, `v0.2.0`, ...
- Tags are signed if possible (`git tag -s`)
- Releases ship with a one-line CHANGELOG entry

---

## 5. How KYC imports it

### 5.1 The import line stays the same

KYC's `services/organism_state/state.py` already imports:

```python
from organism_core import AwarenessEngine
```

After extraction, that same line resolves to the installed package. **Zero source changes in KYC's adapter required.**

### 5.2 requirements.txt change

Add **one** line:

```text
organism-core==0.1.0
```

### 5.3 Failure-tolerance shim (the "KYC must keep working if package fails" guarantee)

KYC must not crash at import time if `organism_core` becomes unimportable (missing install, broken upload, etc.). Add a defensive wrapper in `services/organism_state/__init__.py`:

```python
"""KYC organism state — depends on organism-core but never crashes KYC if it's missing."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from services.organism_state.state import (
        compute_organism_state as _impl_compute,
        write_organism_state_snapshot as _impl_write,
        ORGANISM_STATE_PATH,
    )
    _AWARENESS_AVAILABLE = True
    _IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # organism_core missing or broken
    _AWARENESS_AVAILABLE = False
    _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    logger.error("organism_state: awareness layer unavailable: %s", _IMPORT_ERROR)

    def _impl_compute(**kwargs) -> Dict[str, Any]:
        return {
            "ok": False,
            "organism": "kyc",
            "health_state": "AMBER",
            "reason": "awareness_unavailable",
            "import_error": _IMPORT_ERROR,
            "current_bottleneck": "organism_core_missing",
            "next_recommended_action": (
                "Install organism-core package: "
                "pip install organism-core==<pinned_version>"
            ),
        }

    def _impl_write(state: Dict[str, Any], *, path: Optional[Path] = None) -> Optional[Path]:
        return None

    def ORGANISM_STATE_PATH() -> Path:
        return Path("data/organism_state.json")


def compute_organism_state(**kwargs) -> Dict[str, Any]:
    return _impl_compute(**kwargs)


def write_organism_state_snapshot(state: Dict[str, Any], *, path: Optional[Path] = None) -> Optional[Path]:
    return _impl_write(state, path=path)


__all__ = [
    "compute_organism_state",
    "write_organism_state_snapshot",
    "ORGANISM_STATE_PATH",
]
```

**Blast radius if organism-core disappears:** the `/api/operator/organism/state` endpoint returns `{"ok": False, "reason": "awareness_unavailable"}` with HTTP 200. The control card shows AMBER with "Install organism-core". **Every other part of KYC — intake, queue, VIO, email, payments — continues unaffected.**

### 5.4 Transitional vendored fallback (optional, for the cutover release only)

For the **first KYC release that adopts the package**, ship the vendored copy in parallel:

1. Keep `organism_core/` directory in the KYC repo for one release
2. In the import shim, prefer the installed package; fall back to the vendored copy:

```python
try:
    from organism_core import AwarenessEngine  # installed package
except ImportError:
    from organism_core_vendored import AwarenessEngine  # local fallback
```

Remove the vendored copy in the **next** KYC release once the install path is proven stable in production.

---

## 6. How Purposeful imports it

### 6.1 Identical pattern

Add to Purposeful's `requirements.txt`:

```text
organism-core==0.1.0
```

In Purposeful's awareness adapter (e.g. `services/awareness/state.py`):

```python
from organism_core import (
    AwarenessEngine,
    SignalCollector,
    Check,
    CheckResult,
    Severity,
    RecommendationRegistry,
)

class PurposefulSessionCollector(SignalCollector):
    name = "sessions"
    def collect(self):
        return {"active_count": ...}

class SessionLeakCheck(Check):
    name = "session_leak"
    def evaluate(self, signals):
        n = signals.get("sessions", "active_count", 0)
        ok = n < 10_000
        return CheckResult(
            name=self.name, ok=ok,
            severity=Severity.INFO if ok else Severity.RED,
            detail=f"active sessions={n}",
            evidence={"count": n},
        )

def build_purposeful_engine():
    return AwarenessEngine(
        organism_name="purposeful",
        collectors=[PurposefulSessionCollector(), ...],
        checks=[SessionLeakCheck(), ...],
        recommendations=RecommendationRegistry().register_many({
            "session_leak": "Reset orphaned sessions via /admin/sessions/reset",
        }),
        snapshot_path=Path("/var/data/purposeful_organism_state.json"),
    )
```

### 6.2 Version independence

Purposeful can pin a different version than KYC. Each product chooses its own upgrade cadence:

```text
# KYC
organism-core==0.1.0

# Purposeful
organism-core==0.2.0   # adopted a newer version with extra helpers
```

This is the entire point of pinning — no product can be forced to upgrade by another product's choices.

### 6.3 Same failure-tolerance shim

Purposeful copies the same try/except shim pattern from §5.3, with `"organism": "purposeful"` in the degraded response.

---

## 7. Migration steps

A 9-step, reversible plan. Each step is independently verifiable.

### Step 1 — Create the new repo (no code yet)
- `gh repo create carlvisagie/organism-core --private --description "Reusable self-awareness engine for organisms"`
- Add `LICENSE`, `.gitignore` (Python), `README.md` skeleton
- Create initial `main` branch with empty `pyproject.toml`

### Step 2 — Move code with full git history
- From KYC repo: `git subtree split --prefix=organism_core --branch=organism-core-export`
- Push that branch to the new repo: `git push <organism-core-remote> organism-core-export:main`
- Verify the history shows the original commits (`fabdbc8`, `0422a2d`, `82fd4fe`, ...)

### Step 3 — Add packaging metadata
Create `pyproject.toml` in `organism-core`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "organism-core"
version = "0.1.0"
description = "Domain-agnostic self-awareness engine for software organisms"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Carl Visagie" }]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
]
dependencies = []   # zero runtime deps — pure stdlib

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov"]

[tool.hatch.build.targets.wheel]
packages = ["organism_core"]
```

### Step 4 — Copy tests
- Move `tests/test_organism_core.py` from KYC to `organism-core/tests/test_organism_core.py`
- Verify `pytest -q` is green in the new repo

### Step 5 — Tag v0.1.0
- `git tag -a v0.1.0 -m "Initial extraction from JetFighter_Compliance"`
- `git push --tags`

### Step 6 — Install in KYC (vendored fallback retained)
- Add `organism-core @ git+https://github.com/carlvisagie/organism-core.git@v0.1.0` to KYC's `requirements.txt`
- Apply the failure-tolerance shim (§5.3)
- Keep `organism_core/` directory in KYC as `organism_core_vendored/` fallback
- Update import shim to prefer installed package, fall back to vendored
- **Run KYC full test suite — must be green before merging**

### Step 7 — Deploy KYC with both sources
- Push to Render, watch logs for `[startup] organism_state: using installed organism-core v0.1.0`
- Hit `/api/operator/organism/state` — must return same JSON as before
- Watch for 24–48 hours

### Step 8 — Remove vendored fallback (next KYC release)
- Delete `organism_core_vendored/`
- Delete the fallback branch in the import shim
- Verify CI still green, deploy

### Step 9 — Onboard Purposeful (and any other product)
- Same `pip install` line
- Same `from organism_core import ...`
- Each product writes its own collectors/checks/recommendations
- Each product gets its own `/api/operator/organism/state` endpoint

**Rollback at any step:** revert the KYC commit; the shim falls back to the vendored copy. Zero customer-visible impact.

---

## 8. Test strategy

### 8.1 In `organism-core` repo

- The 18 generic tests from `tests/test_organism_core.py` (current KYC repo) move here unchanged
- CI runs on every PR via GitHub Actions:
  ```yaml
  - name: pytest
    run: pip install -e .[dev] && pytest -q
  ```
- Coverage gate: 90%+ for the core (it's a small, well-bounded surface)
- No KYC-specific test imports allowed (CI fails the build if `services.*` or `server` is imported in any test)

### 8.2 In KYC repo (consumer side)

Three layers of verification:

**Layer A — Contract test:** `tests/test_organism_core_contract.py` (new file in KYC)

```python
"""Verifies the installed organism-core version satisfies KYC's needs.

If organism-core ships an incompatible version (e.g. removes AwarenessEngine
or renames a method), this test fails immediately rather than at runtime.
"""
def test_required_symbols_importable():
    from organism_core import (
        AwarenessEngine, Check, CheckResult, Severity, HealthState,
        SignalCollector, SignalBundle, RecommendationRegistry,
        Pattern, LocationRule, ResidueScanner, ResidueReport,
        derive_health, write_snapshot,
    )

def test_engine_construct_minimal():
    from organism_core import AwarenessEngine, RecommendationRegistry
    AwarenessEngine(
        organism_name="kyc",
        collectors=[],
        checks=[],
        recommendations=RecommendationRegistry(),
    )

def test_snapshot_has_required_keys():
    # build minimal engine, run snapshot, assert required fields
    ...
```

**Layer B — KYC adapter tests:** existing `tests/test_organism_state.py` (15 tests) continues to run against the new install path. Same expectations, same assertions.

**Layer C — Failure-tolerance test:** `tests/test_organism_core_unavailable.py` simulates organism-core missing:

```python
def test_kyc_survives_organism_core_missing(monkeypatch):
    """If the import fails, KYC's endpoint returns AMBER with reason, not crash."""
    monkeypatch.setitem(sys.modules, "organism_core", None)
    # reload services.organism_state — must not raise
    importlib.reload(services.organism_state)
    state = services.organism_state.compute_organism_state()
    assert state["ok"] is False
    assert state["reason"] == "awareness_unavailable"
```

### 8.3 Cross-product compatibility matrix

Once a second product (Purposeful) adopts the package, add a CI matrix in `organism-core`:

```yaml
matrix:
  consumer: [kyc, purposeful]
steps:
  - run: pip install -e .
  - run: |
      git clone ${{ matrix.consumer-repo }}
      cd ${{ matrix.consumer }}
      pip install -r requirements.txt --no-deps
      pip install -e ../organism-core    # use this PR's version
      pytest tests/test_organism_core_contract.py
```

This catches any change in `organism-core` that would break a downstream product, **before the change is merged.**

---

## 9. Release checklist

A release of `organism-core` is not merged to `main` until every item is checked.

### Pre-release (in `organism-core` repo)
- [ ] All tests green on the release branch (`pytest -q`)
- [ ] Coverage ≥ 90% (`pytest --cov=organism_core --cov-fail-under=90`)
- [ ] `pyproject.toml` version bumped
- [ ] `CHANGELOG.md` updated with one human-readable line per change
- [ ] Public surface check: `python -c "import organism_core; print(organism_core.__all__)"` matches the documented contract
- [ ] No new runtime dependencies introduced unless explicitly approved
- [ ] If MAJOR bump: migration notes added to README
- [ ] Cross-product contract tests green (KYC + Purposeful where applicable)

### Release
- [ ] Tag created: `git tag -s vX.Y.Z -m "Release vX.Y.Z"`
- [ ] Tag pushed: `git push --tags`
- [ ] (Optional, once PyPI is set up) `hatch publish`
- [ ] GitHub Release notes generated from CHANGELOG entry

### Post-release (downstream products)
Each consumer decides independently whether and when to upgrade.

For KYC:
- [ ] `requirements.txt` updated to `organism-core==X.Y.Z`
- [ ] `tests/test_organism_core_contract.py` re-run locally
- [ ] Full KYC test suite green (`pytest -q tests/`)
- [ ] Manual smoke: hit `/api/operator/organism/state` against a local server, confirm 200 + valid JSON
- [ ] Deploy to Render
- [ ] Watch logs for 1 hour — no awareness layer errors
- [ ] Watch `/api/operator/organism/state` shows same health state as before
- [ ] If anything regresses: revert the requirements pin; **no force, no rush**

### Emergency rollback
- KYC: change `requirements.txt` back to previous pin, redeploy
- Or: temporarily import-shim raises ImportError to force the failure-tolerance path (degraded but operational)

---

## Non-negotiables (repeated for emphasis)

1. **KYC must keep working** even if `organism-core` becomes unimportable. The §5.3 shim guarantees this.
2. **Pinned versioning only.** No `>=`, no `~`, no `^`, no `main` branch tracking. Ever.
3. **No floating dependency.** The lockfile (or pinned `requirements.txt`) is the production source of truth.
4. **No breaking change without a MAJOR bump.** This is the consumer's contract.
5. **The vendored copy in KYC stays for one release after the cutover.** This is the rollback insurance policy.

---

## Appendix — directory layout target

```
organism-core/                  # new repo
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .github/workflows/test.yml
├── organism_core/              # the package
│   ├── __init__.py             # __all__ defines the public API
│   ├── awareness/
│   ├── health/
│   ├── residue/
│   ├── recommendations/
│   └── persistence/
└── tests/
    └── test_organism_core.py
```

Once this is live, the KYC repo's `organism_core/` directory is deleted (after the one-release fallback window).
