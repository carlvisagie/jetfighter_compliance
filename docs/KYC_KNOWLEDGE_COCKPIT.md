# Solo Operator Knowledge Cockpit

Canonical operator mentor layer inside the KYC platform (`data/knowledge_cockpit/` + `services/knowledge_cockpit/`).

## APIs (ops-protected)

| Method | Path |
|--------|------|
| GET | `/api/operator/knowledge-cockpit` |
| GET | `/api/operator/knowledge-cockpit/search?q=` |
| GET | `/api/operator/knowledge-cockpit/concept/{id}` |
| POST | `/api/operator/knowledge-cockpit/explain` |
| POST | `/api/operator/knowledge-cockpit/context` |

Workflow runbooks remain at `/api/knowledge/*` via `services/knowledge_index.py`.

## Historical import only (never runtime)

- `E:\KYC\Encyclopedia\`
- `E:\KYC_Library\`
- `c:\KYC_Encyclopedia_App\`

One-time: `python scripts/import_legacy_encyclopedia.py --source "..."`  
Rebuild concepts: `python scripts/build_knowledge_cockpit_data.py`

## Memory

Telemetry subsystem `knowledge_cockpit` + timeline `operator_learning_event` on the solo operator entity.
