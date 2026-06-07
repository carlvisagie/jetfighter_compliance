# Acquisition — Architecture

**Owner:** Controlled onboarding / lead validation  
**Canonical detail:** [`../CONTROLLED_ONBOARDING_ACQUISITION.md`](../CONTROLLED_ONBOARDING_ACQUISITION.md), [`../AUTONOMOUS_ACQUISITION_ORGANISM.md`](../AUTONOMOUS_ACQUISITION_ORGANISM.md)

## Purpose

Discover and score prospective customers for founding-pilot outreach. Forensic, memory-bridged — not autonomous outbound spam.

## Inputs

- Connector configs (Reddit, USAspending, etc.) under `services/acquisition/connectors/`
- `KYC_ENABLE_MANUAL_ACQUISITION` env flag
- Intelligence weights (`data/acquisition/intelligence/weights.json`) — bridged island

## Outputs

- Leads under `data/acquisition/leads/`
- Orchestration reports, discovery expansion signals
- Memory bridge via `safe_write_after_acquisition_outcome`
- Operator visibility in control / acquisition panels

## Dependencies

- `services/acquisition/orchestration.py`, `founding_pilot_mode.py`
- Central memory telemetry
- Mock domain blocklist (`is_mock_domain`)

## Failure Modes

- Connector rate limit / auth failure → degraded run, logged
- Mock domain import → rejected at path guard
- Scoring change without approval → forbidden (see AGENTS.md PROTECTED SYSTEMS)
