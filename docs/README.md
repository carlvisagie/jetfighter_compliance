# KeepYourContracts / Jetfighter Compliance — Documentation

**Production repo:** https://github.com/carlvisagie/jetfighter_compliance  
**Product:** KeepYourContracts.com (CMMC, EU DPP, compliance operations)  
**This is NOT the SAGE coaching organism.**

## Production runtime (canonical)

| Environment | Host | Notes |
|-------------|------|--------|
| **Production** | `https://jetfighter-compliance.onrender.com` | Render service `kyc-backend` — same model as Just Talk (hosted, not local PC) |
| **Branded DNS (target)** | `https://compliance.keepyourcontracts.com` | CNAME → Render custom domain (see [`KYC_RENDER_PRODUCTION_CUTOVER.md`](./KYC_RENDER_PRODUCTION_CUTOVER.md)) |
| **Local / tunnel** | `127.0.0.1` + `cloudflared` | **Dev or emergency only** — never for customer production |

Verify Render: `powershell -File scripts/verify-render-production.ps1`

---

## Agents — start here

1. **[`PRODUCTION_ENGINEERING_DOCTRINE.md`](./PRODUCTION_ENGINEERING_DOCTRINE.md)** — **LOCKED** — live URL only; laptop/tunnel never production  
2. **[`AGENTS.md`](./AGENTS.md)** — rules, paths, deploy, do-not-confuse-with-Sage  
3. **Ecosystem stabilization (SAGE repo):**  
   https://github.com/carlvisagie/purposeful-platform/blob/main/docs/STABILIZATION_STATUS_MASTER.md  
4. **KYC live verification:** [`KYC_PRODUCTION_VERIFICATION.md`](./KYC_PRODUCTION_VERIFICATION.md)  
5. **Dependency audit:** [`BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md`](./BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md)  

---

## Code map

| Path | Role |
|------|------|
| `server.py` | FastAPI app, direct onboarding API, static `/ui` mount |
| `ui/shop.html` | **Landing / offers** (PayPal payment links) |
| `ui/inquiry.html` | Contact form |
| `ui/intake.html` | Post-sale client intake |
| `ui/upload.html`, `ui/status.html` | Delivery workflow |
| `organism/` | KYC continuity engine (events, state) |
| `render.yaml` | Render Docker deploy (`kyc-backend`) |
| `drafts/` | Plans (telemetry, shop v2, lead intelligence) — not all wired |

---

## Plans in repo (draft)

| File | Topic |
|------|--------|
| `drafts/lead_intelligence_plan.md` | Autonomous revenue / visitor intelligence |
| `drafts/telemetry_schema_v1.md` | Telemetry event schema |
| `drafts/telemetry_endpoint_plan.md` | Telemetry API plan |
| `organism/docs/TEST_DOCTRINE.md` | KYC organism test doctrine |

---

## Boundary

Do not implement Sage `client_profile`, `sageControlBus`, or coaching Canon here without explicit Owner decision and a written bridge spec in both repos.
