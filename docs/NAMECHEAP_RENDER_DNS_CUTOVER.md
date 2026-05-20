# Namecheap BasicDNS → Render Cutover Guide (Task 31)

**Date:** 2026-05-20  
**Mode:** Owner-facing instructions only — **no code, Render runtime, tunnel, or Blueprint changes**  
**Doctrine:** [`PRODUCTION_ENGINEERING_DOCTRINE.md`](./PRODUCTION_ENGINEERING_DOCTRINE.md)  
**Prior attempt:** [`RENDER_DOMAIN_CUTOVER_RESULT.md`](./RENDER_DOMAIN_CUTOVER_RESULT.md) (Cloudflare — still **530**)

---

## 1. Current state (verified 2026-05-20)

### Render app (healthy — use as rollback URL)

| Check | URL | Result |
|-------|-----|--------|
| Liveness | `https://jetfighter-compliance.onrender.com/healthz` | **PASS** — `{"ok":true,"service":"kyc-backend"}` |

### Branded subdomain (broken — Cloudflare in path)

| Check | URL | Result |
|-------|-----|--------|
| Health | `https://compliance.keepyourcontracts.com/healthz` | **FAIL** — HTTP **530** |
| Shop | `https://compliance.keepyourcontracts.com/ui/shop.html` | **FAIL** — HTTP **530** |

### DNS / nameservers (public lookup)

| Item | Value |
|------|--------|
| **Registrar** | Namecheap (zone `keepyourcontracts.com`) |
| **Active nameservers** | `nico.ns.cloudflare.com`, `dayana.ns.cloudflare.com` |
| **`compliance` resolves to** | Cloudflare anycast (`104.21.28.220`, `172.67.147.184`) |
| **Tunnel in production path** | **No** (530 = CF cannot reach origin; not laptop tunnel) |

**Conclusion:** DNS authority is **Cloudflare**, not Namecheap BasicDNS. Until nameservers change, Namecheap Advanced DNS records **do nothing**.

---

## 2. Target state

```text
Customer
  → https://compliance.keepyourcontracts.com
  → DNS: Namecheap BasicDNS
  → CNAME compliance → jetfighter-compliance.onrender.com
  → Render service kyc-backend (Docker / FastAPI)
  → KYC JSON /healthz + /ui/*

Fallback (always):
  → https://jetfighter-compliance.onrender.com

NOT in path:
  → Cloudflare DNS / proxy / tunnel
  → Carl laptop / cloudflared / localhost / PowerShell windows
```

| Host | Role |
|------|------|
| `compliance.keepyourcontracts.com` | **Canonical branded production** (after cutover) |
| `jetfighter-compliance.onrender.com` | **Permanent fallback** + Render default URL |
| `keepyourcontracts.com` / `www` | **Out of scope** for this guide — configure separately on BasicDNS if needed |

---

## 3. Prerequisites (before changing nameservers)

Complete **in order**:

| # | Action | Where |
|---|--------|--------|
| P1 | Confirm Render app healthy | `Invoke-RestMethod https://jetfighter-compliance.onrender.com/healthz` |
| P2 | **Screenshot / export** Cloudflare DNS records you still need (apex, mail, www) | Cloudflare Dashboard |
| P3 | Add Render custom domain | Render → **kyc-backend** → Settings → **Custom Domains** |
| P4 | Copy Render’s DNS instruction | Render shows required record for `compliance.keepyourcontracts.com` |

**Render custom domain (required):**

1. https://dashboard.render.com/ → **kyc-backend**
2. **Settings** → **Custom Domains** → **Add Custom Domain**
3. Enter: `compliance.keepyourcontracts.com`
4. Render shows verification record(s) — keep this page open

**CNAME target:**

| Source | Target |
|--------|--------|
| Task architecture (expected) | `jetfighter-compliance.onrender.com` |
| **Authority** | **Render Dashboard** — if Render shows a *different* `*.onrender.com` hostname, use **Render’s value**, not this document |

> Render issues TLS for the custom hostname after DNS points correctly and domain shows **Verified** in dashboard.

---

## 4. Exact Namecheap nameserver change

**Location:** Namecheap → **Domain List** → `keepyourcontracts.com` → **Manage** → **Nameservers**

| Step | Action |
|------|--------|
| 1 | Select **Namecheap BasicDNS** (not Custom DNS, not Cloudflare nameservers) |
| 2 | Confirm nameservers become Namecheap defaults, typically: |

```text
dns1.registrar-servers.com
dns2.registrar-servers.com
```

3 | **Save** — allow **24–48 hours** for full NS propagation (often faster, 1–4 hours)

| Before | After |
|--------|-------|
| `nico.ns.cloudflare.com` | `dns1.registrar-servers.com` |
| `dayana.ns.cloudflare.com` | `dns2.registrar-servers.com` |

**Cloudflare side (after NS propagate):**

- Domain may show **Inactive** in Cloudflare — expected.
- **Delete** any `compliance` → `*.cfargotunnel.com` records (historical).
- Do not re-enable Cloudflare proxy for production compliance host.

---

## 5. Exact Namecheap Advanced DNS records

**Location:** Namecheap → `keepyourcontracts.com` → **Advanced DNS**  
(Visible only after nameservers are Namecheap BasicDNS.)

### 5.1 Required for KYC production (compliance subdomain)

| Type | Host | Value | TTL |
|------|------|-------|-----|
| **CNAME** | `compliance` | `jetfighter-compliance.onrender.com.` | Automatic (or 30 min) |

**Notes:**

- Trailing dot on target is optional in Namecheap UI; FQDN is `jetfighter-compliance.onrender.com`.
- **Do not** use Cloudflare proxy — there is none on BasicDNS.
- **Remove** conflicting records for host `compliance` (old A, URL redirect, CNAME to tunnel).

### 5.2 Apex / www (optional — not required for compliance cutover)

Decide separately; examples only:

| Goal | Example record |
|------|----------------|
| Park apex | Namecheap **URL Redirect** or **A** + parking |
| `www` → compliance | **CNAME** `www` → `compliance.keepyourcontracts.com.` |
| Apex → compliance | **URL Redirect** `@` → `https://compliance.keepyourcontracts.com` |

**Mail records:** If you use email on this domain, recreate **MX**, **TXT** (SPF/DKIM) from Cloudflare export before deleting CF DNS.

### 5.3 Records to avoid

| Do not use | Reason |
|------------|--------|
| CNAME → `*.cfargotunnel.com` | Tunnel — not production |
| A record → home IP / laptop | Laptop-dependent |
| Cloudflare nameservers | Keeps 530 / wrong path |

---

## 6. Render custom-domain verification steps

After Namecheap CNAME is saved and NS has propagated:

| Step | Render Dashboard | Pass indicator |
|------|------------------|----------------|
| 1 | **kyc-backend** → Custom Domains | `compliance.keepyourcontracts.com` listed |
| 2 | Wait for DNS detection | Status moves from Pending → **Verified** |
| 3 | Certificate | TLS certificate **Issued** (Let’s Encrypt via Render) |
| 4 | Optional env | `PUBLIC_BASE_URL=https://compliance.keepyourcontracts.com` → Save → Manual Deploy |

**Do not sync `render.yaml` Blueprint** unless Owner explicitly approves.

---

## 7. Public verification commands

Run from any machine with internet — **not** localhost, **not** tunnel.

### 7.1 Before cutover (baseline)

```powershell
# Render fallback — must PASS before and after NS change
Invoke-RestMethod https://jetfighter-compliance.onrender.com/healthz
```

Expected: `ok : True`, `service : kyc-backend`

### 7.2 After NS + CNAME propagate (cutover proof)

```powershell
# 1) JSON health — must be KYC backend (not empty HTML, not 530)
Invoke-RestMethod https://compliance.keepyourcontracts.com/healthz

# 2) UI pages — 200
Invoke-WebRequest https://compliance.keepyourcontracts.com/ui/shop.html -UseBasicParsing
Invoke-WebRequest https://compliance.keepyourcontracts.com/ui/inquiry.html -UseBasicParsing
Invoke-WebRequest https://compliance.keepyourcontracts.com/ui/intake.html -UseBasicParsing

# 3) Fallback still healthy
Invoke-RestMethod https://jetfighter-compliance.onrender.com/healthz
```

### 7.3 DNS sanity (optional)

```powershell
# Nameservers should be Namecheap (not cloudflare.com)
nslookup -type=ns keepyourcontracts.com

# compliance should eventually CNAME to onrender (may show after propagation)
nslookup compliance.keepyourcontracts.com
```

### 7.4 Pass criteria

| Check | Pass |
|-------|------|
| `/healthz` on compliance host | `Content-Type: application/json`, `"ok":true,"service":"kyc-backend"` |
| No 530 / 502 / 503 | All probe URLs return 200 or expected 4xx on APIs |
| `/ui/shop.html` | 200, HTML contains `paypal.com/ncp/payment` |
| Render URL | Still PASS |
| Cloudflare tunnel | **Not required** for traffic |

### 7.5 Fail criteria (stop and rollback DNS)

| Symptom | Likely cause |
|---------|----------------|
| HTTP **530** | Old Cloudflare NS cached, or wrong CNAME, or Render custom domain not verified |
| Empty HTML `/healthz` | Wrong origin (parking page) |
| **404** on `/ui/shop.html` | Points at non-KYC host |
| TLS certificate error | Render domain not verified; wait or fix CNAME |

---

## 8. Rollback steps

If branded host fails after NS change:

| Step | Action |
|------|--------|
| 1 | **Keep serving customers on** `https://jetfighter-compliance.onrender.com` (no code change) |
| 2 | Namecheap Advanced DNS: **remove** or fix `compliance` CNAME |
| 3 | Optional: revert nameservers to Cloudflare (only if you must restore prior CF setup) |
| 4 | Re-verify Render URL `/healthz` |
| 5 | **No git revert required** for DNS-only rollback |

Document rollback time in [`RENDER_DOMAIN_CUTOVER_RESULT.md`](./RENDER_DOMAIN_CUTOVER_RESULT.md) when re-tested.

---

## 9. Expected propagation notes

| Change | Typical propagation |
|--------|---------------------|
| Nameserver → Namecheap BasicDNS | **1–48 hours** globally; plan maintenance window |
| CNAME `compliance` only (NS unchanged) | **5–60 minutes** |
| Render custom domain verify | Minutes after DNS visible to Render |
| TLS certificate | Automatic after verify; up to ~15 minutes |

**During propagation:** Some regions may still hit Cloudflare (530) while others hit Render. Use https://www.whatsmydns.net/ to check NS and CNAME globally.

**TTL:** Lower TTL on old records before migration if Cloudflare allowed; on BasicDNS use Automatic unless lowering for faster rollback.

---

## 10. Owner checklist (copy/paste)

```text
[ ] Render /healthz PASS on jetfighter-compliance.onrender.com
[ ] Export needed DNS from Cloudflare (mail, apex, www)
[ ] Render: add custom domain compliance.keepyourcontracts.com
[ ] Note Render CNAME target: ___________________________
[ ] Namecheap: switch to BasicDNS nameservers (dns1/dns2.registrar-servers.com)
[ ] Wait for NS propagation
[ ] Namecheap Advanced DNS: CNAME compliance → jetfighter-compliance.onrender.com
[ ] Remove compliance tunnel / wrong records in Cloudflare (inactive zone OK)
[ ] Render dashboard: domain Verified + cert Issued
[ ] Invoke-RestMethod https://compliance.keepyourcontracts.com/healthz → JSON ok
[ ] UI shop/inquiry/intake 200
[ ] Update RENDER_DOMAIN_CUTOVER_RESULT.md with PASS
```

---

## 11. Remaining risks (DNS cutover does not fix)

| Risk | Task |
|------|------|
| Ephemeral Render disk / evidence loss | Storage task (S3/R2) |
| `ENVIRONMENT=development` on live | Render env hardening |
| PayPal manual kickoff | PayPal webhook task |
| Apex `keepyourcontracts.com` marketing | Separate DNS decision |

---

## 12. Doctrine closure (this doc commit)

| # | Item | Value |
|---|------|--------|
| 1 | **Commit hash** | *(set after `git push`)* |
| 2 | **Deployed URL** | `https://jetfighter-compliance.onrender.com` (**PASS** at doc write); `https://compliance.keepyourcontracts.com` (**FAIL 530** until Owner executes §4–§6) |
| 3 | **Live verification** | Render `/healthz` **PASS**; branded host **not cut over yet** |
| 4 | **Rollback** | Revert Namecheap NS/CNAME; keep Render URL; no code rollback |
| 5 | **No local-only dependency** | Public probes + registrar/Dashboard instructions only |

**No application code, UI, backend, PayPal, storage, tunnel, or Blueprint changes in Task 31.**

---

## Related docs

| Doc | Purpose |
|-----|---------|
| [`RENDER_PRODUCTION_CUTOVER_PLAN.md`](./RENDER_PRODUCTION_CUTOVER_PLAN.md) | Cloudflare-path plan (superseded for DNS authority by this guide) |
| [`RENDER_DOMAIN_CUTOVER_RESULT.md`](./RENDER_DOMAIN_CUTOVER_RESULT.md) | Record PASS/FAIL after Owner cutover |
| [`PRODUCTION_ENGINEERING_DOCTRINE.md`](./PRODUCTION_ENGINEERING_DOCTRINE.md) | Live-URL-only completion law |
