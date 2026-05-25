# Acquisition tracking (controlled MVP)

**Not a CRM.** Manual CSV + observation notes for 5–15 onboarding validation subjects.

## Files

| File | Use |
|------|-----|
| `tracking.csv` | Funnel per subject (outreach → intake complete) |
| `feedback.csv` | Confusion, friction, trust, wording per subject |
| `observation_log.md` | Human session notes during onboarding |

## Rules

1. One row per **person/company**, not per email blast.  
2. Set `ref` in outreach links (`ref=mvp-aero-001`) — matches inquiry message tag.  
3. Copy `project_id` from ops inbox when inquiry submits.  
4. Mark `intake_completed` only when status shows `intake_received` done.

See `docs/CONTROLLED_ONBOARDING_ACQUISITION.md` for messaging and Sintra worker roles.
