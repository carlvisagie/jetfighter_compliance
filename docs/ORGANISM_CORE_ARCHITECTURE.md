# Organism Core — Architecture

A domain-agnostic self-awareness engine. KYC is the first implementation;
Purposeful, Sage, Just Talk module, Transformation Session module, and
future organisms plug in by providing their own collectors, checks,
recommendations, and residue patterns.

---

## 1. Architecture diagram

```
                                    ┌────────────────────────────────┐
                                    │       organism_core/           │
                                    │  (domain-agnostic, reusable)   │
                                    └────────────────────────────────┘
                                                    │
       ┌───────────────────┬─────────────────┬──────┴──────┬──────────────────┬─────────────────┐
       ▼                   ▼                 ▼             ▼                  ▼                 ▼
  awareness/           health/           residue/    recommendations/    persistence/      __init__.py
   • SignalCollector    • Check            • Pattern    • RecommendationRegistry  • write_snapshot   (public API)
   • SignalBundle       • CheckResult      • LocationRule                                            
   • AwarenessEngine    • Severity         • ResidueScanner                                          
                        • HealthState      • ResidueReport                                           
                        • derive_health                                                              
                                                    │
                                                    │   composes
                                                    ▼
                                ┌───────────────────────────────────────┐
                                │           AwarenessEngine             │
                                │  (registry of collectors + checks +   │
                                │   recommendations + scanner + gating) │
                                └───────────────────────────────────────┘
                                                    │
                                                    │  is plugged with KYC's pieces by:
                                                    ▼
                                ┌───────────────────────────────────────┐
                                │     services/organism_state/          │
                                │     (KYC adapter — first organism)    │
                                │                                       │
                                │   collectors.py    → 6 KYC collectors │
                                │   checks.py        → 8 KYC checks     │
                                │   recommendations  → KYC action map   │
                                │   residue_config   → founding_pilot    │
                                │   state.py         → build_kyc_engine │
                                │                                       │
                                │   Compatibility shims:                │
                                │   detector.py / health.py / residue.py│
                                │   (preserve legacy import surface)    │
                                └───────────────────────────────────────┘
                                                    │
                                                    ▼
                                  GET /api/operator/organism/state
                                  Control card  "Organism state"
                                  data/organism_state.json snapshot
```

### Snapshot pipeline (one call)

```
engine.snapshot()
   │
   ▼
1. each SignalCollector.safe_collect()  ──►  SignalBundle (namespaced)
   │
   ▼
2. ResidueScanner.scan()                ──►  ResidueReport      (optional)
   │                                          merged into bundle["residue"]
   ▼
3. each Check.safe_evaluate(bundle)     ──►  [CheckResult, ...]
   │
   ▼
4. gating(bundle)                       ──►  optional forced-RED tuple
   │
   ▼
5. derive_health(results, gating_failure) ──► HealthVerdict(state, bottleneck, mismatches)
   │
   ▼
6. RecommendationRegistry.recommend()   ──►  next_recommended_action
   │
   ▼
7. compose snapshot dict + write_snapshot(path)
```

---

## 2. Module boundaries

### `organism_core/` — domain-agnostic core

| Submodule          | Public surface                                            | Knows about KYC? |
|--------------------|-----------------------------------------------------------|------------------|
| `awareness/`       | `SignalCollector`, `SignalBundle`, `AwarenessEngine`      | No               |
| `health/`          | `Check`, `CheckResult`, `Severity`, `HealthState`, `derive_health` | No        |
| `residue/`         | `Pattern`, `LocationRule`, `ResidueScanner`, `ResidueReport` | No             |
| `recommendations/` | `RecommendationRegistry`                                  | No               |
| `persistence/`     | `write_snapshot`                                          | No               |

**Hard rule:** any file in `organism_core/` that imports from `services/`,
`server.py`, or any domain-specific module is a bug. The CI residue
scanner can be configured to enforce this if/when desired.

### `services/organism_state/` — KYC adapter (first implementation)

| File                  | Role                                                           |
|-----------------------|----------------------------------------------------------------|
| `collectors.py`       | 6 KYC SignalCollectors (intake, vio, projects, evidence, storage, git) |
| `checks.py`           | 8 KYC Check subclasses                                         |
| `recommendations.py`  | `kyc_recommendations()` registry                               |
| `residue_config.py`   | KYC patterns (`founding_pilot`) + classification rules          |
| `state.py`            | `build_kyc_engine`, `compute_organism_state`, `write_organism_state_snapshot` |
| `detector.py` (shim)  | `run_reconciliation_checks` — preserves legacy test signature  |
| `health.py` (shim)    | `derive_health` — preserves legacy test signature              |
| `residue.py` (shim)   | `scan_repo_for_pilot_residue` — preserves legacy test signature |

**Backward compatibility:** `from services.organism_state import compute_organism_state, write_organism_state_snapshot` works exactly as before. `GET /api/operator/organism/state` returns the same fields. The 15 KYC tests still pass without modification.

---

## 3. Migration plan

### KYC (already complete)

1. ✓ Extract abstractions into `organism_core/`
2. ✓ Rewrite `services/organism_state/state.py` to build an `AwarenessEngine`
3. ✓ Create `collectors.py`, `checks.py`, `recommendations.py`, `residue_config.py`
4. ✓ Keep `detector.py`, `health.py`, `residue.py` as thin shims for legacy tests
5. ✓ Verify all 15 KYC tests still pass
6. ✓ Verify endpoint and control card unchanged

### Future organisms (Purposeful, Sage, Just Talk, Transformation Session)

For each new product:

1. **Add core import path.** If the product is in a separate repo, install `organism_core` as a package. If it lives alongside KYC, just import it.
2. **Define product collectors.** One per source-of-truth (DB, queue, filesystem, API).
3. **Define product checks.** Each check is a `Check` subclass implementing `evaluate(bundle) -> CheckResult`.
4. **Define product recommendations.** Map each check name to a next-action string (or callable).
5. **Define product residue patterns.** Optional — only if the product has deprecated code to track.
6. **Define product gating.** Optional — e.g. "no DB connection = RED".
7. **Construct the engine and expose `<product>_organism_state.json`.**
8. **Add a `/api/operator/organism/state` endpoint** in that product's API surface.

Example (Purposeful):

```python
from organism_core import AwarenessEngine, RecommendationRegistry
from purposeful_organism.collectors import (
    SessionCollector, ChatCollector, MemoryCollector,
)
from purposeful_organism.checks import (
    SessionLeakCheck, MemoryWriteCheck, EmbeddingDriftCheck,
)

engine = AwarenessEngine(
    organism_name="purposeful",
    collectors=[SessionCollector(), ChatCollector(), MemoryCollector()],
    checks=[SessionLeakCheck(), MemoryWriteCheck(), EmbeddingDriftCheck()],
    recommendations=RecommendationRegistry().register_many({
        "session_leak":      "Reset orphaned sessions via /admin/sessions/reset",
        "memory_write":      "Investigate memory writer queue lag",
        "embedding_drift":   "Re-embed corpus from canonical snapshot",
    }),
    snapshot_path=Path("/var/data/purposeful_organism_state.json"),
)
```

---

## 4. Future integration points

| Product                        | Likely collectors                                | Likely checks                                                       | Residue scanner? |
|--------------------------------|--------------------------------------------------|---------------------------------------------------------------------|------------------|
| **KYC** (active)               | intake, vio, projects, evidence, storage, git    | disk_vs_index, queue_vs_vio, evidence_vs_files, pilot_residue (8 total) | yes — founding_pilot |
| **Purposeful**                 | sessions, chats, memory_writes, embeddings        | session_leak, memory_write_lag, embedding_drift, transcript_orphan  | optional        |
| **Sage**                       | conversations, model_calls, billing, queue       | model_quota, billing_drift, queue_starvation, prompt_template_drift | optional        |
| **Just Talk module**           | calls, transcripts, intents                       | transcript_gap, intent_misroute, audio_quality_drop                 | optional        |
| **Transformation Session**     | sessions, outputs, exports                        | session_abandonment, export_failure, generator_drift                | optional        |
| **Cross-organism aggregator**  | one collector per organism's snapshot endpoint   | organism_reachable, organism_red_recently, divergence_check         | no              |

### Cross-organism aggregator (future)

Once two or more organisms exist, a meta-AwarenessEngine can collect each
organism's snapshot endpoint as a SignalCollector and surface them in a
single global health dashboard. Because every snapshot has the same
shape (`health_state`, `current_bottleneck`, `next_recommended_action`),
the aggregator is trivial to build on top of the same core.

### Snapshot contract

Every organism snapshot — regardless of product — has these top-level fields:

```jsonc
{
  "ok": true,
  "organism": "kyc",
  "timestamp_utc": "2026-06-03T10:00:00Z",
  "health_state": "GREEN" | "AMBER" | "RED",
  "current_bottleneck": "<check name or 'none'>",
  "next_recommended_action": "<string>",
  "visibility_mismatches": ["<check name>", ...],
  "checks":   [ { "name", "ok", "severity", "detail", "evidence" }, ... ],
  "signals":  { "<collector_name>": { ... }, ... },
  "residue":  { ... }      // optional, present only if a scanner was registered
  "metadata": { ... }      // product-specific extras
}
```

KYC adds these flattened fields for backward compatibility with the
existing control card and legacy tests. Other organisms are free to
add their own flattened fields if they choose.

---

## 5. Test coverage

| Test file                      | Verifies                                                    | Tests |
|--------------------------------|-------------------------------------------------------------|-------|
| `tests/test_organism_core.py`  | Core abstractions are domain-agnostic and composable        | 18    |
| `tests/test_organism_state.py` | KYC adapter preserves legacy public API                     | 15    |

All 33 tests pass.

---

## 6. Design rules (non-negotiable)

1. **No KYC-specific knowledge in `organism_core/`.** Ever.
2. **Every collector and check must use `safe_collect` / `safe_evaluate`** so one failing piece never breaks the snapshot.
3. **Snapshots are best-effort writes.** Disk failure logs a warning and continues.
4. **Severity is a closed enum.** Don't pass strings except for serialization.
5. **The core never imports from the product.** The product imports from the core.
6. **One organism per `AwarenessEngine`.** Cross-organism aggregation is a separate engine.
