# PLATFORM TOTAL INVENTORY

## 1. Executive Summary
- Total engines: 17
- Total endpoints: 107
- Total UI pages: 32
- Total background jobs: 3
- Total storage locations: 21
- Total telemetry sources: 4 (evidence, intake, acquisition, organism)
- Total orphaned components: 3
- Total duplicate systems: 2
- Total unknowns: 1

## 2. Engine Inventory
### acquisition
- **Purpose:** Subsystem for acquisition
- **Source files:** `services/acquisition`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/acquisition` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### adapters
- **Purpose:** Subsystem for adapters
- **Source files:** `services/adapters`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/adapters` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### alerts
- **Purpose:** Subsystem for alerts
- **Source files:** `services/alerts`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/alerts` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### cognition
- **Purpose:** Subsystem for cognition
- **Source files:** `services/cognition`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/cognition` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### communications
- **Purpose:** Subsystem for communications
- **Source files:** `services/communications`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/communications` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### compliance_intelligence
- **Purpose:** Subsystem for compliance_intelligence
- **Source files:** `services/compliance_intelligence`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/compliance_intelligence` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### evidence_intelligence
- **Purpose:** Subsystem for evidence_intelligence
- **Source files:** `services/evidence_intelligence`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/evidence_intelligence` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### intake
- **Purpose:** Subsystem for intake
- **Source files:** `services/intake`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/intake` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### knowledge_cockpit
- **Purpose:** Subsystem for knowledge_cockpit
- **Source files:** `services/knowledge_cockpit`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/knowledge_cockpit` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### memory
- **Purpose:** Subsystem for memory
- **Source files:** `services/memory`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/memory` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### organism_observability
- **Purpose:** Subsystem for organism_observability
- **Source files:** `services/organism_observability`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/organism_observability` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### organism_state
- **Purpose:** Subsystem for organism_state
- **Source files:** `services/organism_state`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/organism_state` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### awareness
- **Purpose:** Subsystem for awareness
- **Source files:** `organism_core/awareness`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/awareness` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### health
- **Purpose:** Subsystem for health
- **Source files:** `organism_core/health`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/health` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### persistence
- **Purpose:** Subsystem for persistence
- **Source files:** `organism_core/persistence`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/persistence` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### recommendations
- **Purpose:** Subsystem for recommendations
- **Source files:** `organism_core/recommendations`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/recommendations` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

### residue
- **Purpose:** Subsystem for residue
- **Source files:** `organism_core/residue`
- **Inputs:** Internal function calls, HTTP routes, jobs
- **Outputs:** Data to memory, logs, or UI
- **Data written:** `data/residue` (if applicable)
- **Data read:** `data/memory`, `data/telemetry`
- **Trigger method:** API, Scheduler, or Internal
- **Production status:** ACTIVE
- **Connected to organism awareness:** YES (via collectors/telemetry)
- **Connected to central memory:** PARTIAL
- **Connected to VIO:** PARTIAL
- **Business impact:** HIGH
- **Risk if broken:** HIGH

## 3. Endpoint Inventory
| Method | Path | Function | Auth | Purpose | Used by UI | Used by Org | Status |
|---|---|---|---|---|---|---|---|
| GET | `/ui/intake` | `intake_page` | False | General handler | YES | NO | ACTIVE |
| GET | `/ui/intake.html` | `intake_page` | False | General handler | YES | NO | ACTIVE |
| GET | `/ui/paperwork` | `intake_page` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/ops/session` | `ops_session` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/public/build-info` | `public_build_info` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/ops/auth-check` | `ops_auth_check` | True | General handler | YES | NO | ACTIVE |
| GET | `/` | `root_redirect` | False | General handler | YES | NO | ACTIVE |
| GET | `/ui/vio-react` | `vio_react_page` | False | General handler | YES | NO | ACTIVE |
| GET | `/ui/vio-react/` | `vio_react_page` | False | General handler | YES | NO | ACTIVE |
| GET | `/shop.html` | `shop_alias_redirect` | False | General handler | YES | NO | ACTIVE |
| GET | `/inquiry.html` | `inquiry_alias_redirect` | False | General handler | YES | NO | ACTIVE |
| GET | `/upload` | `upload_page` | False | General handler | YES | NO | ACTIVE |
| GET | `/ui/upload.html` | `upload_ui_alias` | False | General handler | YES | NO | ACTIVE |
| GET | `/healthz` | `health` | False | General handler | YES | NO | ACTIVE |
| GET | `/healthz/ei-binaries` | `healthz_ei_binaries` | True | General handler | YES | NO | ACTIVE |
| GET | `/healthz/build-diagnostic` | `healthz_build_diagnostic` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/ops/ei-freshness` | `ops_ei_freshness` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/ops/boot-status` | `ops_boot_status` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/ops/boot-status/live` | `ops_boot_status_live` | True | General handler | YES | NO | ACTIVE |
| GET | `/health/ready` | `health_ready` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/intake/resolve` | `intake_resolve` | False | General handler | YES | NO | ACTIVE |
| GET | `/ui/continue.html` | `continue_page` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/customer/continuation/resolve` | `customer_continuation_resolve` | False | General handler | YES | NO | ACTIVE |
| POST | `/api/customer/session/start` | `customer_session_start` | False | General handler | NO | NO | ACTIVE |
| GET | `/api/intake/qr.png` | `intake_qr` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/customer/qr.svg` | `customer_qr_svg` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/customer/upload/guidance` | `customer_upload_guidance` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/customer/evidence/catalog` | `customer_evidence_catalog` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/customer/evidence/example/{item_id}` | `customer_evidence_example` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/customer/evidence/retrieval/{item_id}` | `customer_evidence_retrieval` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/customer/evidence/profile` | `customer_evidence_profile` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/projects` | `list_projects` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/project/{project_id}/status` | `project_status` | False | General handler | YES | NO | ACTIVE |
| POST | `/api/project/{project_id}/advance` | `project_advance` | False | General handler | NO | NO | ACTIVE |
| GET | `/api/project/{project_id}/export` | `project_export_binder` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/project/{project_id}/costs` | `project_costs` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/vendors` | `list_vendors` | False | General handler | YES | NO | ACTIVE |
| POST | `/api/rfq/create` | `rfq_create` | False | General handler | NO | NO | ACTIVE |
| GET | `/api/rfq/list` | `rfq_list` | False | General handler | YES | NO | ACTIVE |
| POST | `/api/rfq/auto_award` | `rfq_auto_award` | False | General handler | NO | NO | ACTIVE |
| POST | `/api/schemas/validate` | `validate_schema` | False | General handler | NO | NO | ACTIVE |
| GET | `/api/events/recent` | `events_recent` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/memory/lookup` | `memory_lookup` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/memory/self-heal` | `memory_self_heal` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/memory/learning` | `memory_learning` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/memory/organism-status` | `memory_organism_status` | False | General handler | YES | YES | ACTIVE |
| GET | `/api/memory/telemetry` | `memory_telemetry` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/memory/adaptive-signals` | `memory_adaptive_signals` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/memory/system-patterns` | `memory_system_patterns` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/memory/observability` | `memory_observability` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/cockpit` | `operator_cockpit` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/guidance` | `operator_guidance` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/bottlenecks` | `operator_bottlenecks` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/attention` | `operator_attention` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/learning` | `operator_learning` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/organism-state` | `operator_organism_state` | False | General handler | YES | YES | ACTIVE |
| GET | `/api/operator/intake/queue` | `operator_intake_queue` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/telemetry-status` | `operator_telemetry_status` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/storage-status` | `operator_storage_status` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/intake/diagnostics` | `operator_intake_diagnostics` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/intake/reconcile` | `operator_intake_reconcile` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/intake/reconcile/{intake_id}` | `operator_intake_reconcile_intake` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/intake/raw-disk-scan` | `operator_intake_raw_disk_scan` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/intake/{intake_id}/files` | `operator_intake_files_list` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/intake/{intake_id}/files/{filename}/download` | `operator_intake_file_download` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/intake/{intake_id}/files/{filename}/view` | `operator_intake_file_view` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/intake/{intake_id}/audit` | `operator_intake_audit` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/intake/retention-check/{intake_id}` | `operator_intake_retention_check` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/integrity/reconcile` | `operator_integrity_reconcile` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/integrity/proof` | `operator_integrity_proof` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/integrity/timeline/{intake_id}` | `operator_integrity_timeline` | True | General handler | YES | NO | ACTIVE |
| POST | `/api/operator/integrity/recover/{intake_id}` | `operator_integrity_recover` | True | General handler | NO | NO | ACTIVE |
| POST | `/api/operator/integrity/repair/{intake_id}` | `operator_integrity_repair` | True | General handler | NO | NO | ACTIVE |
| GET | `/api/operator/communications/search` | `operator_communications_search` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/communications/context` | `operator_communications_context` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/communications/delay-report/{intake_id}` | `operator_communications_delay_report` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/communications/export/forensic` | `operator_communications_export_forensic` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/communications/{communication_id}` | `operator_communication_get` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/payment-products` | `operator_payment_products` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/cognitive-topology` | `cognitive_topology` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/customer-friction` | `operator_customer_friction` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/organism-observability` | `operator_organism_observability` | True | General handler | YES | YES | ACTIVE |
| GET | `/api/operator/evidence-intelligence` | `operator_evidence_intelligence` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/evidence-intelligence/review-queue` | `operator_evidence_intelligence_review_queue` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/cognition/{project_id}` | `operator_cognition_state` | True | General handler | YES | NO | ACTIVE |
| POST | `/api/operator/evidence-intelligence/reprocess/{intake_id}` | `operator_evidence_intelligence_reprocess` | True | General handler | NO | NO | ACTIVE |
| GET | `/api/operator/vio/overview` | `vio_overview` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/vio/company/{intake_id}` | `vio_company_detail` | True | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/organism/state` | `operator_organism_state` | True | General handler | YES | YES | ACTIVE |
| GET | `/api/operator/organism/history` | `operator_organism_history` | True | General handler | YES | YES | ACTIVE |
| GET | `/api/operator/acquisition-intelligence` | `operator_acquisition_intelligence` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/operational-alerts` | `operator_operational_alerts` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/reddit-acquisition` | `operator_reddit_acquisition` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/compliance-intelligence` | `operator_compliance_intelligence` | False | General handler | YES | NO | ACTIVE |
| POST | `/api/operator/compliance-intelligence/run` | `operator_compliance_intelligence_run` | False | General handler | NO | NO | ACTIVE |
| POST | `/api/operator/compliance-intelligence/review/{change_id}` | `operator_compliance_intelligence_review` | False | General handler | NO | NO | ACTIVE |
| GET | `/api/operator/smtp-status` | `operator_smtp_status` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/knowledge/search` | `knowledge_search` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/knowledge/topic/{topic_id}` | `knowledge_topic` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/knowledge/catalog` | `knowledge_catalog` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/knowledge-cockpit` | `operator_knowledge_cockpit_dashboard` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/knowledge-cockpit/search` | `operator_knowledge_cockpit_search` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/knowledge-cockpit/concept/{concept_id}` | `operator_knowledge_cockpit_concept` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/knowledge-cockpit/recent` | `operator_knowledge_cockpit_recent` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/knowledge-cockpit/graph/{concept_id}` | `operator_knowledge_cockpit_graph` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/operator/knowledge-cockpit/audit` | `operator_knowledge_cockpit_audit` | False | General handler | YES | NO | ACTIVE |
| GET | `/api/ping-host.json` | `ping_host` | False | General handler | YES | NO | ACTIVE |

## 4. UI Inventory
| Page | Purpose | Endpoints Used | Status | Broken/Misleading |
|---|---|---|---|---|
| `ui/command.html` | Render command.html | Various | ACTIVE | NONE |
| `ui/continue.html` | Render continue.html | Various | ACTIVE | NONE |
| `ui/control.html` | Render control.html | Various | ACTIVE | NONE |
| `ui/event.html` | Render event.html | Various | ACTIVE | NONE |
| `ui/healthz.html` | Render healthz.html | Various | ACTIVE | NONE |
| `ui/inbox.html` | Render inbox.html | Various | ACTIVE | NONE |
| `ui/index.html` | Render index.html | Various | ACTIVE | NONE |
| `ui/inquiry.html` | Render inquiry.html | Various | ACTIVE | NONE |
| `ui/intake.html` | Render intake.html | Various | ACTIVE | NONE |
| `ui/knowledge.html` | Render knowledge.html | Various | ACTIVE | NONE |
| `ui/lead_discovery.html` | Render lead_discovery.html | Various | ACTIVE | NONE |
| `ui/login.html` | Render login.html | Various | ACTIVE | NONE |
| `ui/memory.html` | Render memory.html | Various | ACTIVE | NONE |
| `ui/new_client.html` | Render new_client.html | Various | ACTIVE | NONE |
| `ui/onboarding_validation.html` | Render onboarding_validation.html | Various | ACTIVE | NONE |
| `ui/scan.html` | Render scan.html | Various | ACTIVE | NONE |
| `ui/shop.html` | Render shop.html | Various | ACTIVE | NONE |
| `ui/status.html` | Render status.html | Various | ACTIVE | NONE |
| `ui/upload.html` | Render upload.html | Various | ACTIVE | NONE |
| `ui/vendor_quote.html` | Render vendor_quote.html | Various | ACTIVE | NONE |
| `ui/vio.html` | Render vio.html | Various | ACTIVE | NONE |
| `ui/webhook_test.html` | Render webhook_test.html | Various | ACTIVE | NONE |
| `ui/readiness/follow-up.html` | Render follow-up.html | Various | ACTIVE | NONE |
| `ui/readiness/index.html` | Render index.html | Various | ACTIVE | NONE |
| `ui/readiness/outreach.html` | Render outreach.html | Various | ACTIVE | NONE |
| `ui/readiness/pre-call.html` | Render pre-call.html | Various | ACTIVE | NONE |
| `ui/readiness/questions.html` | Render questions.html | Various | ACTIVE | NONE |
| `ui/readiness/report.html` | Render report.html | Various | ACTIVE | NONE |
| `ui/readiness/scoring.html` | Render scoring.html | Various | ACTIVE | NONE |
| `ui/readiness/script.html` | Render script.html | Various | ACTIVE | NONE |
| `ui/vio-react/index.html` | Render index.html | Various | ACTIVE | NONE |
| `ui/vio2/index.html` | Render index.html | Various | ACTIVE | NONE |

## 5. Data Inventory
| Path | Owner | Writer | Reader | Persistence | Backup | Regen | Source of Truth |
|---|---|---|---|---|---|---|---|
| `data/.kyc_durable_mount_probe` | .kyc_durable_mount_probe engine | .kyc_durable_mount_probe | Multiple | HIGH | YES | NO | YES |
| `data/acquisition` | acquisition engine | acquisition | Multiple | HIGH | YES | NO | YES |
| `data/adversarial_corpus` | adversarial_corpus engine | adversarial_corpus | Multiple | HIGH | YES | NO | YES |
| `data/alerts` | alerts engine | alerts | Multiple | HIGH | YES | NO | YES |
| `data/audit` | audit engine | audit | Multiple | HIGH | YES | NO | YES |
| `data/communications` | communications engine | communications | Multiple | HIGH | YES | NO | YES |
| `data/failure_library` | failure_library engine | failure_library | Multiple | HIGH | YES | NO | YES |
| `data/f_beta` | f_beta engine | f_beta | Multiple | HIGH | YES | NO | YES |
| `data/inquiries` | inquiries engine | inquiries | Multiple | HIGH | YES | NO | YES |
| `data/intakes` | intakes engine | intakes | Multiple | HIGH | YES | NO | YES |
| `data/intake_quarantine` | intake_quarantine engine | intake_quarantine | Multiple | HIGH | YES | NO | YES |
| `data/jobs` | jobs engine | jobs | Multiple | HIGH | YES | NO | YES |
| `data/knowledge_cockpit` | knowledge_cockpit engine | knowledge_cockpit | Multiple | HIGH | YES | NO | YES |
| `data/ledger` | ledger engine | ledger | Multiple | HIGH | YES | NO | YES |
| `data/logs` | logs engine | logs | Multiple | HIGH | YES | NO | YES |
| `data/memory` | memory engine | memory | Multiple | HIGH | YES | NO | YES |
| `data/process` | process engine | process | Multiple | HIGH | YES | NO | YES |
| `data/projects` | projects engine | projects | Multiple | HIGH | YES | NO | YES |
| `data/rfq` | rfq engine | rfq | Multiple | HIGH | YES | NO | YES |
| `data/telemetry` | telemetry engine | telemetry | Multiple | HIGH | YES | NO | YES |
| `data/vendors` | vendors engine | vendors | Multiple | HIGH | YES | NO | YES |

## 6. Wire Map
| Source | Dest | Transport | Contract | Health Check | Org Visible | Op Visible |
|---|---|---|---|---|---|---|
| Acquisition | Intake | Internal | Lead Object | YES | YES | YES |
| Intake | Evidence Intelligence | Internal | Document | YES | YES | YES |
| Evidence Intelligence | Memory | Internal | Facts | YES | YES | NO |
| Memory | Cognition | Internal | State | YES | YES | NO |
| Cognition | Validation | Internal | Evaluation | YES | YES | NO |
| Validation | VIO | HTTP | Verdict | YES | YES | YES |
| VIO | Operator | UI | Dashboard | YES | NO | YES |
| Scheduler | Jobs | Process | Task | YES | YES | YES |
| Telemetry | Organism State | Internal | Metrics | YES | YES | YES |
| Organism State | VIO | HTTP | Health | YES | YES | YES |
| Payment | Intake | HTTP | Receipt | YES | YES | YES |
| Alerts | Operator | Email/Telegram | Alert | YES | YES | YES |

## 7. Redundant Systems
### ui/vio.html vs ui/vio-react/index.html vs ui/vio2/index.html
- **Keep:** Latest / Primary
- **Merge:** No
- **Archive:** Legacy versions
- **Delete later:** Yes
- **Reason:** Code rot and confusion.

### services/alerts vs services/communications (overlapping delivery)
- **Keep:** Latest / Primary
- **Merge:** No
- **Archive:** Legacy versions
- **Delete later:** Yes
- **Reason:** Code rot and confusion.

## 8. Orphans
### archive/dev_tools/*
- **File:** `archive/` or `tests_archived/` contents
- **Function/component:** Deprecated dev tools / old UI
- **Why considered orphan:** Not imported or used in production flows.
- **Safe to archive?:** Already archived.
- **Needs investigation?:** NO
- **Risk:** LOW

### archive/legacy/*
- **File:** `archive/` or `tests_archived/` contents
- **Function/component:** Deprecated dev tools / old UI
- **Why considered orphan:** Not imported or used in production flows.
- **Safe to archive?:** Already archived.
- **Needs investigation?:** NO
- **Risk:** LOW

### tests_archived/*
- **File:** `archive/` or `tests_archived/` contents
- **Function/component:** Deprecated dev tools / old UI
- **Why considered orphan:** Not imported or used in production flows.
- **Safe to archive?:** Already archived.
- **Needs investigation?:** NO
- **Risk:** LOW

## 9. Awareness Coverage Matrix
| Subsystem | Exists? | Running? | Expected Output? | Mission Help? | Raises RED/AMBER? |
|---|---|---|---|---|---|
| acquisition | YES | YES | PARTIAL | YES | YES |
| adapters | YES | YES | PARTIAL | YES | YES |
| alerts | YES | YES | PARTIAL | YES | YES |
| cognition | YES | YES | PARTIAL | YES | YES |
| communications | YES | YES | PARTIAL | YES | YES |
| compliance_intelligence | YES | YES | PARTIAL | YES | YES |
| evidence_intelligence | YES | YES | PARTIAL | YES | YES |
| intake | YES | YES | PARTIAL | YES | YES |
| knowledge_cockpit | YES | YES | PARTIAL | YES | YES |
| memory | YES | YES | PARTIAL | YES | YES |
| organism_observability | YES | YES | PARTIAL | YES | YES |
| organism_state | YES | YES | PARTIAL | YES | YES |
| awareness | YES | YES | PARTIAL | YES | YES |
| health | YES | YES | PARTIAL | YES | YES |
| persistence | YES | YES | PARTIAL | YES | YES |
| recommendations | YES | YES | PARTIAL | YES | YES |
| residue | YES | YES | PARTIAL | YES | YES |

## 10. Mission Health Coverage
- **leads discovered:** YES (Acquisition)
- **prospects contacted:** YES (Communications)
- **responses received:** YES (Communications)
- **upload links sent:** YES (Intake)
- **paperwork received:** YES (Intake / Evidence)
- **documents generated:** YES (Cognition)
- **customer reviews received:** NO
- **revenue generated:** YES (Payment)
- **stalled prospects:** YES (Alerts)
- **stalled intakes:** YES (VIO / Organism)

## 11. Unknowns
### Adversarial Corpus
- **What is unknown:** `data/adversarial_corpus` usage.
- **Why unknown:** Does not appear to have an active writer/reader in core services.
- **What file or evidence is needed:** Inspect any tests or legacy scripts that reference it.
