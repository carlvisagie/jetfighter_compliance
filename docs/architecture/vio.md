# VIO (Visual Intelligence Observatory) — Architecture

**Owner:** Operator experience  
**Canonical detail:** [`../VIO_CONSTITUTION.md`](../VIO_CONSTITUTION.md), [`../VIO_DOCTRINE.md`](../VIO_DOCTRINE.md)

## Purpose

Unified operator view of every company’s compliance journey — L1 spine, L2 depth, environment truth ribbon. Read-only against production APIs.

## Inputs

- `GET /api/operator/vio/overview`
- `GET /api/cognitive-topology`
- Per-company intake / EI / cognition summaries
- `GET /api/operator/environment-label`

## Outputs

- `ui/vio.html` + `vio-frontend/` React bundle (`ui/vio-react/`)
- Stage urgency, attention strip, document visibility tiles
- Configure API connection state (must reflect live organism, not empty config)

## Dependencies

- Intake queue + project IDs (`FB-*`)
- Evidence intelligence + cognition artifacts
- Ops session auth
- Build pipeline: `vio-frontend` → static bundle copy

## Failure Modes

- Stale React bundle vs source → misleading UI labels (rebuild required)
- Missing EI → KPI tiles empty but must not fabricate counts
- NON-PRODUCTION ribbon → all counts untrusted per doctrine
