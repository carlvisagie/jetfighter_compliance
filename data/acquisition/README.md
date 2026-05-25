# Acquisition (controlled MVP)

**Not a CRM.** Lead discovery + manual funnel tracking.

## Lead Discovery Engine

| Path | Use |
|------|-----|
| `leads/import_candidates.csv` | Paste owner/Sintra candidates, then run import script |
| `leads/leads.jsonl` / `leads.csv` | Scored lead store (append-only import) |
| `leads/review_queue.csv` | fit ≥ 65, needs owner review |
| `reports/latest_discovery_report.md` | Last import summary |

```bash
python scripts/acquisition_import_candidates.py
```

See `docs/LEAD_DISCOVERY_ENGINE.md` and `/ui/lead_discovery.html`.

## Onboarding funnel tracking

| File | Use |
|------|-----|
| `tracking.csv` | Funnel per subject (outreach → intake complete) |
| `feedback.csv` | Confusion, friction, trust, wording |
| `observation_log.md` | Human session notes |

Use `ref=<lead_id>` from discovery handoff links. See `docs/CONTROLLED_ONBOARDING_ACQUISITION.md`.
