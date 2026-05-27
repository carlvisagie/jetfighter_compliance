# Solo Operator Knowledge Cockpit

Canonical operator mentor layer inside the KYC platform (`data/knowledge_cockpit/` + `services/knowledge_cockpit/`).

Doctrine: `docs/KYC_ORGANISM_DOCTRINE.md`

## Contextual Knowledge Overlay

Embedded in `ui/control.html` — collapsible panel via **Explain view** and per-item **Explain** on Reddit, compliance, and evidence. Not a separate app.

## APIs (ops-protected)

| Method | Path |
|--------|------|
| GET | `/api/operator/knowledge-cockpit` |
| GET | `/api/operator/knowledge-cockpit/search?q=` |
| GET | `/api/operator/knowledge-cockpit/concept/{id}` |
| GET | `/api/operator/knowledge-cockpit/graph/{id}` |
| GET | `/api/operator/knowledge-cockpit/recent` |
| GET | `/api/operator/knowledge-cockpit/audit` |
| POST | `/api/operator/knowledge-cockpit/explain` |
| POST | `/api/operator/knowledge-cockpit/context` |
| POST | `/api/operator/knowledge-cockpit/overlay` |

Workflow runbooks remain at `/api/knowledge/*` via `services/knowledge_index.py`.

## Historical import only (never runtime)

- `E:\KYC\Encyclopedia\`
- `E:\KYC_Library\`
- `c:\KYC_Encyclopedia_App\`

One-time: `python scripts/import_legacy_encyclopedia.py --source "..."`  
Rebuild concepts: `python scripts/build_knowledge_cockpit_data.py`

## Memory

Telemetry subsystem `knowledge_cockpit` + timeline `operator_learning_event` on the solo operator entity.
