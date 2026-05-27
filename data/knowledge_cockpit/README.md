# Knowledge Cockpit data (canonical)

All operator encyclopedia knowledge for production lives under this directory inside the KYC platform repo/runtime.

## Files

| File | Purpose |
|------|---------|
| `concepts.json` | Operational compliance concepts (mentor layer) |
| `relationships.json` | Concept graph edges |
| `authoritative_sources.json` | Curated public publication URLs |
| `control_matrix.json` | Control family → evidence type hints |
| `control_family_xref.json` | Cross-family reference map |
| `operator_learning.jsonl` | Operator learning signals (append-only) |
| `recent_lookups.jsonl` | Recent concept lookups (append-only) |

## Historical import sources (not used at runtime)

These paths were used **once** to seed data. Deployed code must **never** read them:

- `E:\KYC\Encyclopedia\` (single-file HTML encyclopedia v3.2)
- `E:\KYC_Library\` (`library.json` / `library.csv`)
- `c:\KYC_Encyclopedia_App\` (Electron offline mirror)
- `c:\KYC_Shadow\` (setup script backup only)

Optional one-time import: `python scripts/import_legacy_encyclopedia.py` (requires explicit `--source` path).

## Runbooks

Operator workflow documentation remains in `docs/*.md` and is indexed by `services/knowledge_index.py`. The Knowledge Cockpit **combines** runbooks + concepts in the operator UI/API.
