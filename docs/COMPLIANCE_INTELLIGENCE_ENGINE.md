# Continuous Compliance Intelligence Engine (v1)

Keeps the KYC organism aware of changes at **authoritative public** compliance and regulatory sources. Findings feed central memory, telemetry, operator cockpit, and knowledge recommendations — never a separate brain.

## Architecture

```
APScheduler (services.engine)
  → daily / weekly compliance jobs
  → run_compliance_cycle()
       → fetcher (httpx, caching headers)
       → snapshots (hash + excerpt)
       → change_detector
       → classifier (rule-based)
       → impact_mapper → review_queue
       → memory_bridge → central memory timeline
       → telemetry (subsystem: compliance_intel)
       → knowledge_bridge (recommendations only)
```

**Control Center** (`/ui/control.html`) is the primary operator surface. An optional Electron encyclopedia sync app may mirror knowledge offline; it does not own compliance truth.

## Data layout

| Path | Purpose |
|------|---------|
| `data/compliance_intelligence/sources.json` | Curated source registry |
| `data/compliance_intelligence/snapshots/<source_id>/` | Append-only HTML snapshots + index |
| `data/compliance_intelligence/changes.jsonl` | Detected changes |
| `data/compliance_intelligence/impacts.jsonl` | Mapped impacts |
| `data/compliance_intelligence/review_queue.jsonl` | Operator review queue |
| `data/compliance_intelligence/digests/` | Weekly operator digests (JSON) |

Canonical operational truth for the organism: **central memory** timeline on entity `KYC Compliance Intelligence Watch` plus telemetry.

## Authoritative sources (v1)

Seeded in `sources.py` / `sources.json`:

- NIST CSRC, SP 800-171, SP 800-53  
- Cyber AB, DoD CIO CMMC  
- DFARS, FAR, Federal Register  
- CISA cybersecurity advisories  
- NARA CUI Registry  
- DDTC / ITAR  
- SAM.gov (reference)  
- EU Digital Product Passport / ESPR  

## Safety rules

- **Not legal advice** — all operator copy includes disclaimers.  
- **No certification guarantees** from automated monitoring.  
- **No customer auto-publication** — `customer_auto_publish` is always false in v1.  
- **No auto-update** of customer upload guidance or deliverables without operator approval.  
- **Public URLs only** — no logged-in scraping, LinkedIn, or abusive crawling.  
- **Respectful fetching** — User-Agent identification, timeouts, retries, `If-None-Match` / `If-Modified-Since`.  
- **Operator APIs only** — `/api/operator/compliance-intelligence*` requires ops auth.  
- **No secrets in logs** — errors truncated; snapshot excerpts capped.

## Review workflow

1. Scheduler or operator runs `POST /api/operator/compliance-intelligence/run`.  
2. Changes create **review queue** items (`pending`).  
3. Operator reviews in Control Center → Compliance Intelligence Watch.  
4. `POST /api/operator/compliance-intelligence/review/{change_id}` with `approved` | `dismissed` | `deferred`.  
5. Approved items may inform manual updates to docs/knowledge — **knowledge_bridge never writes files automatically**.

## Memory & telemetry

| Timeline event | When |
|----------------|------|
| `compliance_source_checked` | After each fetch attempt |
| `compliance_change_detected` | Hash/title/phrase change |
| `compliance_impact_classified` | Impact record created |
| `compliance_review_required` | Review queue item |
| `knowledge_update_recommended` | Topic suggestion (no auto-apply) |

Telemetry subsystem: `compliance_intel` — `fetch_started`, `fetch_completed`, `fetch_failed`, `change_detected`, `impact_classified`, `review_queued`, `source_stale`, `source_unreachable`.

## APIs

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/operator/compliance-intelligence` | Ops |
| POST | `/api/operator/compliance-intelligence/run` | Ops |
| POST | `/api/operator/compliance-intelligence/review/{change_id}` | Ops |

## Limitations (v1)

- Rule-based classification — no LLM summarization in production path.  
- HTML text extraction is naive (no full legal parsing).  
- Some government sites may block automated access; failures surface as `source_unreachable`.  
- Weekly digest is JSON for operators — **no customer emails**.  
- Stale detection uses `last_seen_utc` threshold (default 14 days).

## Future enhancement path

- Semantic diff summaries (optional AI, offline review queue only).  
- RSS/Atom feeds where publishers provide them.  
- Tighter coupling to operator guidance priorities.  
- Approved knowledge patches via PR workflow from review UI.

## Related

- [CENTRAL_MEMORY.md](./CENTRAL_MEMORY.md)  
- [KYC_CONSTITUTION.md](./KYC_CONSTITUTION.md)  
- [EVIDENCE_INTELLIGENCE_LAYER.md](./EVIDENCE_INTELLIGENCE_LAYER.md)  
- [LAUNCH_PATH.md](./LAUNCH_PATH.md)
