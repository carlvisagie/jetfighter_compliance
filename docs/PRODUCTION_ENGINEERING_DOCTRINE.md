# Production Engineering Doctrine — KeepYourContracts (KYC)

**Status:** LOCKED (Task 26)  
**Applies to:** `carlvisagie/jetfighter_compliance`, Render service `kyc-backend`, all agents and operators  
**Related:** [`BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md`](./BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md), [`KYC_RENDER_PRODUCTION_CUTOVER.md`](./KYC_RENDER_PRODUCTION_CUTOVER.md)

---

## Core law

1. **Build exactly the way it will be used.**  
   Production is Render Docker + public HTTPS URL + hosted env vars + durable platform storage — not a Windows laptop, not a tunnel, not a local venv habit path.

2. **Test exactly where it will be used.**  
   Run verification against the **deployed** service after `main` is pushed and Render (or successor host) has finished deploy.

3. **Verify only on the live deployed URL.**  
   The canonical proof host is the current production URL (today: `https://jetfighter-compliance.onrender.com`, or the active Render custom domain once DNS is cut over).

---

## Non-negotiables

| Rule | Meaning |
|------|---------|
| **localhost is never completion proof** | `127.0.0.1`, local uvicorn, or “works in Postman on my machine” does not close a task. |
| **Tunnels are never production** | Cloudflare Tunnel / `cloudflared` is dev or emergency preview only — never customer ingress. |
| **Local PowerShell is never production** | `start_everything.ps1`, `start_live_platform.ps1`, `fix_everything.ps1`, etc. are not deploy or runtime truth. |
| **Laptop-dependent runtime is never production** | If closing Carl’s laptop breaks customer-facing behavior, the architecture is **invalid**. |
| **No task is complete until verified on deployed public URL** | Every delivery ends with live HTTP checks on the public host. |
| **GitHub `main` + hosted deployment are canonical truth** | Repo commit on `main` + running image on Render (or documented successor) define what “shipped” means. |
| **Every feature must include live URL verification** | New routes, UI, env, DNS, or payment behavior → probe the real URL in the task record. |
| **If closing the laptop breaks it, architecture is invalid** | Same as laptop-dependent rule — no exceptions for “we’ll tunnel later.” |

---

## Canonical production surface

| Item | Value |
|------|--------|
| **Repo** | https://github.com/carlvisagie/jetfighter_compliance |
| **Branch** | `main` |
| **Host (interim)** | `https://jetfighter-compliance.onrender.com` |
| **Branded target** | `https://compliance.keepyourcontracts.com` (when DNS + Render custom domain are correct) |
| **Surface verifier** | `powershell -File scripts/verify-render-production.ps1` |
| **Full lock verifier** | `powershell -File scripts/verify-production-live.ps1` (after Owner env/DNS) |

**Dev-only (never task completion):** `127.0.0.1`, `.venv`, `.env`, `E:\JetFighter_Compliance` / local clone paths, `cloudflared`, open PowerShell launcher windows.

---

## Task completion acceptance criteria (every future task)

No task is **DONE** until the deliverable documents all five:

| # | Requirement | Example |
|---|-------------|---------|
| 1 | **Commit hash** | `e0e95b1` on `main` |
| 2 | **Deployed URL** | `https://jetfighter-compliance.onrender.com/ui/shop.html` |
| 3 | **Live verification result** | Verifier exit code, HTTP status, or explicit probe output (pass/fail) |
| 4 | **Rollback note** | “Revert commit X and redeploy”; or “Restore Render env var Y to previous value” |
| 5 | **No local-only dependency** | Confirm feature does not require laptop, tunnel, or uncommitted local files |

Optional but recommended: link to a short result doc (`docs/KYC_*_RESULT.md`) with probe timestamp (UTC).

---

## What agents must do

**Before claiming complete:**

1. Push (or confirm) changes on `origin/main`.
2. Wait for hosted deploy (Render autoDeploy or documented manual deploy).
3. Run live probes on the **public** URL (script or documented `curl`/PowerShell).
4. Record commit hash + URL + pass/fail in the task summary or result doc.
5. State rollback (git revert + redeploy, or dashboard env rollback).

**Forbidden as “done”:**

- “Verified locally” only  
- “Tunnel is up”  
- “Works on E: drive”  
- “Docs updated” without live URL proof  
- “Should work after deploy” without post-deploy probe  

---

## What operators must do

- Treat Render Dashboard env + **Custom Domains** as production control plane — not `.env` on a PC.  
- Never point branded DNS at `*.cfargotunnel.com` for production.  
- Use [`BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md`](./BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md) for fragility; use **this doctrine** for how every task must close.

---

## Alignment with ecosystem docs

KYC stabilization status is also tracked in the SAGE repo:  
https://github.com/carlvisagie/purposeful-platform/blob/main/docs/STABILIZATION_STATUS_MASTER.md  

When KYC production posture changes, update that file per Owner process (cross-repo, not a substitute for live URL proof in this repo).

---

## Doctrine lock (Task 26)

| Field | Value |
|-------|--------|
| **Locked** | 2026-05-20 |
| **Task** | TASK 26 — Production Engineering Doctrine Lock |
| **Enforcement** | All agents read `docs/AGENTS.md` + this file before production-impacting work |
