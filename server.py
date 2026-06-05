
import logging, json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

try:
    from fastapi import FastAPI
except Exception as e:
    print("FASTAPI import failed:", e)

from fastapi import FastAPI, Request, HTTPException, Form, UploadFile, File, Body, Response
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# --- Services & config ---
from services.config import ROOT, DATA, LOGS, SETTINGS, PROJECTS
from services.security import make_intake_token, parse_intake_token, make_continuation_token
from services.adapters.generic import extract_generic
from services.public_url import get_public_base_url
from services.production import (
    startup_warnings,
    readiness_checks,
    require_ops_access,
    safe_upload_filename,
    validate_project_id,
    is_production,
)
from services.projects import new_project
from services.emails import send_email
from services.ledger import register_artifact, record_event
from services.process import compute_status, mark_done, init_workflow, set_phase
from services.engine import enqueue, start_worker
from services.external import compute_external_costs
from services.validator import REGISTRY
from drafts.telemetry_fastapi_endpoint import router as telemetry_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = FastAPI(title="KeepYourContracts.com  Compliance Control Panel", version="1.0.0")


@app.get("/ui/intake")
@app.get("/ui/intake.html")
@app.get("/ui/paperwork")
def intake_page():
    """Canonical customer paperwork submission page."""
    return FileResponse(ROOT / "ui" / "intake.html")




app.include_router(telemetry_router)

# CORS — production policy:
#   - In production: lock to known surfaces (custom domain + Render backend).
#   - Outside production: allow * for local dev / preview environments / tests.
# Operators can override via CORS_ALLOW_ORIGINS (comma-separated) without code change.
import os as _os_cors

_ENV_CORS = (_os_cors.getenv("CORS_ALLOW_ORIGINS") or "").strip()
if _ENV_CORS:
    _CORS_ORIGINS = [o.strip() for o in _ENV_CORS.split(",") if o.strip()]
elif (_os_cors.getenv("ENVIRONMENT") or "").lower() == "production":
    _CORS_ORIGINS = [
        "https://compliance.keepyourcontracts.com",
        "https://jetfighter-compliance.onrender.com",
    ]
else:
    _CORS_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/ui", StaticFiles(directory=str(ROOT / "ui"), html=True), name="ui")


@app.middleware("http")
async def ops_auth_middleware(request: Request, call_next):
    from services.ops_auth import gate_request

    if request.url.path in ("/healthz", "/api/ops/boot-status"):
        return await call_next(request)
    blocked = gate_request(request)
    if blocked is not None:
        return blocked
    response = await call_next(request)
    path = request.url.path
    # ── Cache discipline ────────────────────────────────────────────────────
    # Background (2026-06-05 "WTF?" incident): the previous policy was
    # `Cache-Control: public, max-age=3600` for /ui/assets/*. That meant
    # browsers kept stale CSS/JS for an hour after every deploy. Operators
    # who reloaded the page during that window saw an HTML pointing at
    # cached CSS that no longer matched the renderer the HTML had loaded.
    # The L2-mount overlay fix shipped but operators saw a dark page until
    # they remembered to hard-refresh. Unacceptable for a primary surface.
    #
    # New policy (cheaper than it sounds — most responses are 304 Not
    # Modified, no body transfer):
    #   - /ui/assets/*  → no-cache, must-revalidate
    #       Browser caches the file but MUST revalidate with the server on
    #       every request. If the file hasn't changed, server returns 304
    #       (no body). If it has, fresh bytes ship. Operator never sees
    #       stale CSS/JS again.
    #   - /ui/*.html    → unchanged (no-cache, must-revalidate)
    if path.startswith("/ui/assets/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif path.startswith("/ui/") and (path.endswith(".html") or path in ("/ui", "/ui/")):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


@app.middleware("http")
async def env_envelope_middleware(request: Request, call_next):
    """
    Production-Is-The-Only-Truth contract: every operator JSON response carries
    the environment envelope so no count can ever be quoted without provenance.

    See docs/PRODUCTION_IS_THE_ONLY_TRUTH.md.

    - For dict JSON: injects `_env` key (additive — backward compatible).
    - For list / non-dict JSON: body untouched; envelope returned via the
      `X-Env-Envelope` HTTP header so the contract still holds.
    - Always sets `X-Env-Envelope` header for /api/operator/* responses.
    """
    response = await call_next(request)
    path = request.url.path
    if not path.startswith("/api/operator/"):
        return response

    from services.env_envelope import env_envelope as _env_envelope

    env = _env_envelope()
    env_header_json = json.dumps(env, separators=(",", ":"))

    content_type = (response.headers.get("content-type") or "").lower()
    is_json = "application/json" in content_type

    if not is_json:
        response.headers["X-Env-Envelope"] = env_header_json
        return response

    body_bytes = b""
    async for chunk in response.body_iterator:
        body_bytes += chunk if isinstance(chunk, (bytes, bytearray)) else chunk.encode("utf-8")

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        new_headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        new_headers["X-Env-Envelope"] = env_header_json
        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=new_headers,
            media_type=response.media_type,
        )

    if isinstance(payload, dict):
        payload["_env"] = env

    new_body = json.dumps(payload, default=str).encode("utf-8")
    new_headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    new_headers["X-Env-Envelope"] = env_header_json
    return Response(
        content=new_body,
        status_code=response.status_code,
        headers=new_headers,
        media_type="application/json",
    )


@app.get("/api/operator/environment-label")
async def operator_environment_label(request: Request):
    """UI ribbon source — see services/env_envelope.environment_label()."""
    require_ops_access(request)
    from services.env_envelope import environment_label

    return environment_label()


# ---------- Operator auth ----------
@app.post("/api/ops/login")
async def ops_login(body: dict = Body(...), response: Response = None):
    from services.ops_auth import (
        create_session_token,
        ops_password_configured,
        set_session_cookie,
        verify_ops_password,
    )

    if not ops_password_configured():
        raise HTTPException(status_code=503, detail="OPS_PASSWORD not configured")
    password = str(body.get("password") or "")
    if not verify_ops_password(password):
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_session_token()
    out = JSONResponse({"ok": True})
    set_session_cookie(out, token)
    return out


@app.post("/api/ops/logout")
async def ops_logout():
    from services.ops_auth import clear_session_cookie

    out = JSONResponse({"ok": True})
    clear_session_cookie(out)
    return out


@app.get("/api/ops/session")
def ops_session(request: Request):
    from services.ops_auth import (
        auth_contract,
        is_authenticated,
        ops_api_key_configured,
        ops_password_configured,
    )

    return {
        "ok": True,
        "authenticated": is_authenticated(request),
        "password_configured": ops_password_configured(),
        "api_key_configured": ops_api_key_configured(),
        "auth_contract": auth_contract(),
    }


@app.get("/api/public/build-info")
def public_build_info():
    from services.build_info import public_build_info as _public_build_info

    return {"ok": True, **_public_build_info()}


@app.get("/api/ops/auth-check")
def ops_auth_check(request: Request):
    from services.build_info import public_build_info, service_name
    from services.durable_storage import active_data_root
    from services.ops_auth import describe_request_auth_mode
    from services.production import require_ops_access

    require_ops_access(request)
    mode = describe_request_auth_mode(request)
    pub = public_build_info()
    return {
        "ok": True,
        "auth_mode": mode,
        "service": service_name(),
        "environment": pub["environment"],
        "git_commit": pub["git_commit"],
        "data_root": str(active_data_root().resolve()),
    }


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/ui/shop.html", status_code=302)


@app.get("/shop.html")
def shop_alias_redirect():
    return RedirectResponse(url="/ui/shop.html", status_code=302)


@app.get("/inquiry.html")
def inquiry_alias_redirect():
    return RedirectResponse(url="/ui/inquiry.html", status_code=302)


@app.get("/upload")
def upload_page():
    return FileResponse(ROOT / "ui" / "upload.html")


@app.get("/ui/upload.html")
def upload_ui_alias():
    return FileResponse(ROOT / "ui" / "upload.html")

# === PATCH INSERT START ===
def safe_load_json(path):
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[CONFIG FAIL] {e} - Configuration file is required for production!")
        raise RuntimeError("Configuration file 'config_auth.json' is missing or invalid. Cannot start application.")

cfg = {}
# === PATCH INSERT END ===


# ---------- Startup ----------
@app.on_event("startup")
async def _boot_worker():
    from services.runtime_boot import (
        audit_boot_env,
        enforce_safe_mode_required,
        is_safe_mode,
        log_boot,
        schedulers_enabled,
    )

    log_boot("application", "starting", "stabilization boot")
    audit_boot_env()
    enforce_safe_mode_required()

    from services.durable_storage import log_storage_boot_status

    log_storage_boot_status()

    try:
        from services.intake.retention import scan_retention_at_startup
        from services.intake.storage import legacy_migration_status

        scan_retention_at_startup()
        legacy_migration_status()
        if not is_safe_mode():
            from services.intake.forensic_reconcile import run_forensic_reconciliation

            run_forensic_reconciliation()
    except Exception as exc:
        logging.critical("[retention] startup scan failed: %s", exc)

    for w in startup_warnings():
        logging.warning("[startup] %s", w)
        log_boot("startup_warning", "warn", w[:200])

    if is_safe_mode() or not schedulers_enabled():
        log_boot(
            "worker",
            "skipped",
            f"safe_mode={is_safe_mode()} schedulers={schedulers_enabled()}",
        )
        log_boot("heavy_subsystems", "skipped", "inquiry/upload/static only")
    else:
        try:
            start_worker(heavy=True)
            log_boot("worker", "started", "heavy=True")
        except Exception as exc:
            log_boot(
                "worker",
                "start_failed",
                f"{type(exc).__name__}: {exc}",
            )
            logging.exception("[boot] start_worker failed: %s", exc)


def _safe_mode_block(module: str = "acquisition") -> Optional[JSONResponse]:
    """POST run endpoints — 503 with paused payload, no heavy imports before guard."""
    from services.runtime_boot import module_pause_payload, should_pause_module

    if not should_pause_module(module):
        return None
    return JSONResponse(status_code=503, content=module_pause_payload(module))


# ---------- Health ----------
@app.get("/healthz")
def health():
    """Liveness — no I/O, no schedulers (Render healthCheckPath)."""
    from services.runtime_boot import is_safe_mode, schedulers_enabled

    return {
        "ok": True,
        "service": "kyc-backend",
        "safe_mode": is_safe_mode(),
        "schedulers_enabled": schedulers_enabled(),
    }


@app.get("/healthz/ei-binaries")
def healthz_ei_binaries():
    """Unauthenticated runtime probe for Evidence-Intelligence binaries.

    Reports whether the OCR + PDF rasterisation stack is actually
    resolvable inside the running container. Without these, the
    evidence-intelligence layer silently degrades to
    ``ocr_binary_unavailable`` for every customer scan and we lose
    the single biggest quality lift in the extraction pipeline.

    Returns a small JSON payload with one row per dependency so the
    operator (and the awareness layer) can tell at a glance whether
    OCR is real or a paper tiger:

      {
        "ok": true,
        "ocr_enabled": true,            # KYC_OCR_ENABLED app-level flag
        "pytesseract_import": "ok",
        "pdf2image_import":   "ok",
        "tesseract_binary":   {"available": true, "version": "5.3.0"},
        "poppler_binary":     {"available": true, "version": "..."}
      }

    Unauthenticated on purpose: this is a liveness / capability probe
    with no PII surface, the same way ``/healthz`` is unauthenticated.
    Used by both the deployment loop and the operator UI to verify
    that OCR is genuinely live after a deploy.
    """
    import os
    import shutil
    import subprocess

    out = {
        "ok":          True,
        "ocr_enabled": (os.getenv("KYC_OCR_ENABLED", "").lower() in ("1","true","yes","on")),
    }

    # Python import surface.
    try:
        import pytesseract  # noqa: F401
        out["pytesseract_import"] = "ok"
    except Exception as exc:
        out["pytesseract_import"] = f"missing: {type(exc).__name__}"
        out["ok"] = False
    try:
        import pdf2image  # noqa: F401
        out["pdf2image_import"] = "ok"
    except Exception as exc:
        out["pdf2image_import"] = f"missing: {type(exc).__name__}"
        out["ok"] = False

    def _probe_binary(executable: str, version_arg: str) -> dict:
        path = shutil.which(executable)
        if not path:
            return {"available": False, "reason": "not_on_PATH"}
        try:
            r = subprocess.run(
                [path, version_arg],
                capture_output=True, text=True, timeout=5,
            )
            ver = (r.stdout or r.stderr or "").splitlines()[0].strip()[:120]
            return {"available": True, "path": path, "version": ver}
        except Exception as exc:
            return {"available": False, "path": path,
                    "reason": f"{type(exc).__name__}: {exc}"}

    out["tesseract_binary"] = _probe_binary("tesseract", "--version")
    out["poppler_binary"]   = _probe_binary("pdftoppm",  "-v")
    if not out["tesseract_binary"].get("available"):
        out["ok"] = False
    if not out["poppler_binary"].get("available"):
        out["ok"] = False

    return out


@app.get("/api/ops/ei-freshness")
def ops_ei_freshness(request: Request, dry_run: bool = True):
    """Run the EI freshness sweep on demand and return its report.

    Default is ``dry_run=true`` — compute staleness signals without
    triggering any reprocess. Set ``?dry_run=false`` to actually run
    reprocess for stale intakes (subject to the same per-sweep
    throttle the scheduler uses).

    Doctrine: this is the operator-visible window into an otherwise-
    autonomous process. The scheduler is the primary path; this
    endpoint exists so an operator can answer "what's the organism
    seeing right now?" without grepping logs. Auth-gated because the
    payload names intake IDs."""
    from services.evidence_intelligence.freshness import sweep_intakes_for_staleness
    from services.production import require_ops_access

    require_ops_access(request)
    summary = sweep_intakes_for_staleness(dry_run=bool(dry_run))
    return {"ok": True, **summary}


@app.get("/api/ops/boot-status")
def ops_boot_status():
    """Operator-visible startup log (env audit, safe mode, scheduler kill-switch)."""
    import os

    from services.runtime_boot import boot_log_snapshot, is_safe_mode, schedulers_enabled

    return {
        "ok": True,
        "KYC_SAFE_MODE_raw": os.getenv("KYC_SAFE_MODE"),
        "safe_mode_effective": is_safe_mode(),
        "schedulers_enabled": schedulers_enabled(),
        "scan_type": "boot_snapshot",
        **boot_log_snapshot(),
    }


@app.get("/api/ops/boot-status/live")
def ops_boot_status_live(request: Request):
    """Live disk scan + forensic proof — NOT the cached boot snapshot."""
    from services.intake.proof_gate import build_live_boot_status
    from services.production import require_ops_access

    require_ops_access(request)
    return build_live_boot_status()


@app.get("/health/ready")
def health_ready(deep: bool = False):
    """Readiness — data dirs + config flags (monitoring; not used by Render default)."""
    checks = readiness_checks()
    core_ok = checks["data_writable"] and checks["projects_dir"]
    status = "ready" if core_ok else "degraded"
    if deep:
        try:
            from services.memory.telemetry import emit_telemetry
            from services.memory import run_self_healing_scan

            heal = run_self_healing_scan(write_suggestions=False)
            orphan_n = len(heal.get("orphan_projects") or [])
            emit_telemetry(
                "health",
                "memory_orphan_count",
                severity="info" if orphan_n < 5 else "warning",
                success=True,
                metadata={"orphan_projects": orphan_n, "entity_count": heal.get("entity_count", 0)},
            )
            if not checks.get("smtp_configured"):
                emit_telemetry("health", "smtp_unconfigured", severity="warning", success=False)
            if not checks.get("data_writable"):
                emit_telemetry("health", "data_not_writable", severity="critical", success=False)
            if status == "degraded":
                emit_telemetry("health", "service_degraded", severity="warning", success=False, message=status)
            if not core_ok:
                emit_telemetry("health", "readiness_failed", severity="error", success=False, metadata=checks)
        except Exception:
            pass
    return {"ok": core_ok, "status": status, "checks": checks}

# ---------- Internal helper ----------
def _find_project_by_order(order_id: str) -> Optional[str]:
    prefix = f"P-{order_id}-"
    matches = sorted(PROJECTS.glob(f"{prefix}*"), reverse=True)
    return matches[0].name if matches else None


def kickoff(order_id: str, email: str, name: str, skus: list):
    from services.durable_storage import reject_demo_order_in_production

    reject_demo_order_in_production(order_id)
    try:
        from services.memory import safe_read_before_kickoff

        safe_read_before_kickoff(email, name)
    except Exception:
        pass
    existing = _find_project_by_order(order_id)
    if existing:
        token = make_intake_token(existing, email)
        base = get_public_base_url()
        intake_url = f"{base}/ui/intake?token={token}"
        try:
            from services.customer_friction import get_or_issue_continuation

            cont = get_or_issue_continuation(existing, email)
            continuation_url = cont["continuation_url"]
            continuation_token = cont["continuation_token"]
            upload_url = f"{base}/upload?project_id={existing}&token={continuation_token}"
        except Exception:
            continuation_url = f"{base}/ui/continue.html"
            continuation_token = make_continuation_token(existing, email)
            upload_url = f"{base}/upload?project_id={existing}"
        return {
            "ok": True,
            "project_id": existing,
            "intake_url": intake_url,
            "upload_url": upload_url,
            "continuation_url": continuation_url,
            "continuation_token": continuation_token,
            "existing": True,
        }
    meta = new_project(order_id, email, name, skus)
    try:
        init_workflow(meta["project_id"], skus)
        set_phase(meta["project_id"], "INTAKE")
    except Exception as e:
        logging.error(f"Failed to initialize workflow for project {meta['project_id']}: {e}")

    token = make_intake_token(meta["project_id"], email)
    base = get_public_base_url()
    intake_url = f"{base}/ui/intake?token={token}"
    try:
        from services.customer_friction import get_or_issue_continuation

        cont = get_or_issue_continuation(meta["project_id"], email)
        continuation_url = cont["continuation_url"]
        continuation_token = cont["continuation_token"]
        upload_url = f"{base}/upload?project_id={meta['project_id']}&token={continuation_token}"
    except Exception:
        continuation_url = f"{base}/ui/continue.html"
        continuation_token = make_continuation_token(meta["project_id"], email)
        upload_url = f"{base}/upload?project_id={meta['project_id']}"
    html = f"""
    <h2>You are set up — upload what you have</h2>
    <p>Give us exactly what you already have. You do not need perfect or organized paperwork.</p>
    <p><strong><a href="{upload_url}">Upload my paperwork</a></strong></p>
    <p>Continue on your phone anytime (no password):<br><a href="{continuation_url}">{continuation_url}</a></p>
    <p>Optional quick details: <a href="{intake_url}">{intake_url}</a></p>
    <p><small>Project reference: {meta['project_id']}. This is operational assistance, not legal advice or a certification guarantee.</small></p>
    """
    try:
        send_email(email, "Upload your paperwork — KeepYourContracts", html)
    except Exception as e:
        logging.warning(f"Email failed to send to {email}: {e}")

    evt_id = f"EVT-{meta['project_id']}-ORDER"
    record_event({
        "event_id": evt_id,
        "event_type": "ATTEST",
        "why": "Onboarding started; project created",
        "when_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "who": {"name":"System","role":"Automation","email":"noreply@keepyourcontracts.com"},
        "where": {"address":"System"},
        "what": [{"id": meta["project_id"], "qty": 1}],
        "prev_hash": "GENESIS",
        "hash": "temp"
    })
    try:
        from services.memory import safe_link_after_kickoff, safe_link_ledger_event

        safe_link_after_kickoff(meta["project_id"], order_id, email, name, skus)
        safe_link_ledger_event(
            evt_id,
            meta["project_id"],
            email=email,
            name=name,
            event_type="ATTEST",
            why="Onboarding started; project created",
        )
    except Exception:
        pass
    return {
        "ok": True,
        "project_id": meta["project_id"],
        "intake_url": intake_url,
        "upload_url": upload_url,
        "continuation_url": continuation_url,
        "continuation_token": continuation_token,
    }

# ---------- Onboarding kickoff (direct; no Shopify) ----------
@app.post("/events/payment/test")
async def events_payment_test(request: Request, evt: dict):
    require_ops_access(request)
    try:
        order_id, email, name, skus = extract_generic(evt)
    except (KeyError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")
    if not email:
        raise HTTPException(status_code=400, detail="email required")
    res = kickoff(order_id, email, name, skus)
    try:
        enqueue("post_payment", {"order_id": order_id, "email": email, "name": name, "skus": skus})
    except Exception as e:
        logging.warning(f"Queue enqueue failed for order {order_id}: {e}")
    return res

# ---------- Inquiry (contact form) ----------
@app.post("/api/inquiry/submit")
async def inquiry_submit(
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
):
    payload = {
        "name": name,
        "email": email,
        "subject": subject,
        "message": message,
        "received_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    inquiries_dir = DATA / "inquiries"
    inquiries_dir.mkdir(parents=True, exist_ok=True)
    safe_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (inquiries_dir / f"inquiry-{safe_id}.json").write_text(json.dumps(payload, indent=2))
    html = (
        f"<h3>Inquiry from {name}</h3>"
        f"<p><b>Email:</b> {email}<br><b>Subject:</b> {subject}</p>"
        f"<pre>{message}</pre>"
    )
    notify_to = SETTINGS.digest_email_to or SETTINGS.smtp_from_email
    if notify_to:
        try:
            send_email(notify_to, f"Inquiry: {subject}", html)
        except Exception as e:
            logging.warning("Inquiry notify email failed: %s", e)
    logging.info("Inquiry received from %s <%s>: %s", name, email, subject)
    order_id = f"INQ-{safe_id}"
    skus = [subject.strip()[:80] or "GENERAL-INQUIRY"]
    try:
        res = kickoff(order_id, email, name or email, skus)
        from services.acquisition.forensics import safe_record_inquiry

        safe_record_inquiry(res["project_id"], email, name, subject, message, order_id)
        return {
            "ok": True,
            "project_id": res["project_id"],
            "intake_url": res["intake_url"],
            "upload_url": res.get("upload_url"),
            "continuation_url": res.get("continuation_url"),
            "continuation_token": res.get("continuation_token"),
        }
    except Exception as e:
        logging.exception("Inquiry kickoff failed for %s: %s", email, e)
        return {"ok": True, "kickoff": False, "detail": "Inquiry saved; project creation failed"}


# ---------- Intake ----------
@app.get("/api/intake/resolve")
def intake_resolve(token: str):
    try:
        info = parse_intake_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    project_id = info["p"]
    email = info.get("e", "")
    out = {"ok": True, "project_id": project_id, "email": email}
    try:
        from services.customer_friction import get_or_issue_continuation, build_resume_state

        cont = get_or_issue_continuation(project_id, email)
        state = build_resume_state(project_id, email)
        out["continuation_url"] = cont["continuation_url"]
        out["upload_url"] = state.get("upload_url")
        out["progress_percent"] = state.get("progress_percent")
        out["momentum_message"] = state.get("momentum_message")
    except Exception:
        pass
    return out


# /ui/intake, /ui/intake.html, /ui/paperwork are all served by the canonical
# intake_page() handler defined at the top of this module (see line ~43).

@app.post("/api/intake/submit")
async def intake_submit(
    token: str = Form(...),
    company: str = Form(""),
    contact: str = Form(""),
    phone: str = Form(""),
    notes: str = Form(""),
    ext_cmmc_l2_c3pao: str = Form(None),
    ext_soc2: str = Form(None),
    ext_iso27001: str = Form(None),
    ext_pci: str = Form(None),
    ext_qes: str = Form(None),
    ext_esign: str = Form(None),
    ext_tsa: str = Form(None),
    ext_gs1: str = Form(None),
    ext_lab_ce: str = Form(None),
    ext_lab_substance: str = Form(None),
    ext_pentest: str = Form(None),
    ext_vulnscan: str = Form(None),
    ext_privacy_counsel: str = Form(None),
    ext_bg_checks: str = Form(None),
    ext_worm: str = Form(None),
    ext_translation: str = Form(None),
    ext_docusign: str = Form(None),
    ext_eidas: str = Form(None),
    ext_lab_tests: str = Form(None),
    ext_vuln_scans: str = Form(None),
    ext_legal: str = Form(None),
    ext_background: str = Form(None),
):
    ext_esign = ext_esign or ext_docusign
    ext_qes = ext_qes or ext_eidas
    ext_lab_ce = ext_lab_ce or ext_lab_tests
    ext_vulnscan = ext_vulnscan or ext_vuln_scans
    ext_privacy_counsel = ext_privacy_counsel or ext_legal
    ext_bg_checks = ext_bg_checks or ext_background
    try:
        info = parse_intake_token(token)
    except Exception:
        raise HTTPException(401, "Invalid token")
    project_id = info["p"]
    pdir = DATA / "projects" / project_id
    if not pdir.exists():
        raise HTTPException(404, "Project not found")

    intake = {
        "company": company, "contact": contact, "phone": phone, "notes": notes,
        "external_flags": {
            "cmmc_l2_c3pao": bool(ext_cmmc_l2_c3pao),
            "soc2": bool(ext_soc2),
            "iso27001": bool(ext_iso27001),
            "pci": bool(ext_pci),
            "qes": bool(ext_qes),
            "esign": bool(ext_esign),
            "tsa": bool(ext_tsa),
            "gs1": bool(ext_gs1),
            "lab_ce": bool(ext_lab_ce),
            "lab_substance": bool(ext_lab_substance),
            "pentest": bool(ext_pentest),
            "vulnscan": bool(ext_vulnscan),
            "privacy_counsel": bool(ext_privacy_counsel),
            "bg_checks": bool(ext_bg_checks),
            "worm": bool(ext_worm),
            "translation": bool(ext_translation)
        }
    }
    (pdir / "communications").mkdir(parents=True, exist_ok=True)
    (pdir / "communications" / "intake.json").write_text(json.dumps(intake, indent=2))

    # flip the checklist item if present
    try:
        cl_path = pdir / "checklist.json"
        cl = json.loads(cl_path.read_text())
        for t in cl:
            # Use ID if available, fallback to title matching
            if t.get("id") in ("intake_form", "intake_received") or t.get("title", "").lower().startswith(
                "client intake form"
            ):
                t["status"] = "done"
        cl_path.write_text(json.dumps(cl, indent=2))
    except Exception as e:
        logging.warning(f"Failed to update checklist for project {project_id}: {e}")

    try:
        mark_done(project_id, "intake_received")
        set_phase(project_id, "INTAKE")
        from services.memory.organism_integration import safe_write_after_workflow

        safe_write_after_workflow(
            project_id,
            step_id="intake_received",
            phase="INTAKE",
            email=info.get("e", ""),
        )
    except Exception as e:
        logging.warning("Workflow intake_received mark failed for %s: %s", project_id, e)

    from services.acquisition.forensics import safe_record_intake

    safe_record_intake(project_id, info.get("e", ""), intake)

    try:
        from services.customer_friction import get_or_issue_continuation, record_continuation_event

        cont = get_or_issue_continuation(project_id, info.get("e", ""))
        record_continuation_event(
            cont["continuation_token"],
            "continuation_completed",
            step="intake",
        )
        upload_url = f"{get_public_base_url()}/upload?project_id={project_id}&token={cont['continuation_token']}"
    except Exception:
        upload_url = f"{get_public_base_url()}/upload?project_id={project_id}"
    return {
        "ok": True,
        "project_id": project_id,
        "upload_url": upload_url,
    }

# ---------- Customer friction (continuation, QR, guidance) ----------
@app.get("/ui/continue.html", response_class=HTMLResponse)
def continue_page():
    return FileResponse(str(ROOT / "ui" / "continue.html"))


@app.get("/api/customer/continuation/resolve")
def customer_continuation_resolve(token: str, client: str = "unknown"):
    from services.customer_friction import resolve_continuation

    return resolve_continuation(token, client=client)


@app.post("/api/customer/continuation/event")
async def customer_continuation_event(body: dict = Body(...)):
    from services.customer_friction import record_continuation_event

    token = str(body.get("token") or "")
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    return record_continuation_event(
        token,
        str(body.get("event_type") or "continuation_completed"),
        step=str(body.get("step") or ""),
        client=str(body.get("client") or "unknown"),
        duration_ms=body.get("duration_ms"),
        metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
    )


@app.post("/api/telemetry/customer-beacon")
async def customer_telemetry_beacon(body: dict = Body(default={})):
    from services.organism_observability.beacon import record_customer_beacon

    meta = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
    return record_customer_beacon(
        str(body.get("event_type") or "upload_page_view"),
        session_id=str(body.get("session_id") or ""),
        project_id=str(body.get("project_id") or ""),
        duration_ms=body.get("duration_ms"),
        metadata=meta,
    )


@app.post("/api/customer/session/start")
def customer_session_start():
    from services.customer_session import start_session

    return start_session()


@app.post("/api/customer/session/upload")
async def customer_session_upload(
    session_id: str = Form(...),
    session_token: str = Form(...),
    file: UploadFile = File(...),
):
    from services.customer_session import upload_to_session

    return await upload_to_session(session_id, session_token, file)


@app.post("/api/customer/session/complete")
async def customer_session_complete(
    session_id: str = Form(...),
    session_token: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    note: str = Form(""),
):
    from services.customer_session import complete_session

    return complete_session(session_id, session_token, name, email, note)


@app.post("/api/intake/upload")
async def intake_upload(
    request: Request,
    files: List[UploadFile] = File(...),
    intake_id: str = Form(""),
    token: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    company: str = Form(""),
    context: str = Form(""),
    deadline: str = Form(""),
    ref: str = Form(""),
    expected_file_count: int = Form(0),
    expected_file_names: str = Form(""),
    upload_manifest: str = Form(""),
):
    from services.intake.intake import process_upload
    from services.intake.integrity import parse_expected_file_names, parse_upload_manifest

    xf = request.headers.get("x-forwarded-for") or ""
    client_host = request.client.host if request.client else ""
    return await process_upload(
        files,
        intake_id=intake_id.strip(),
        token=token.strip(),
        email=email,
        phone=phone,
        company=company,
        context=context,
        deadline=deadline,
        ref=ref.strip(),
        expected_file_count=expected_file_count,
        expected_file_names=parse_expected_file_names(expected_file_names),
        upload_manifest=parse_upload_manifest(upload_manifest),
        request_metadata={
            "source_ip": xf.split(",")[0].strip() if xf else client_host,
            "x-forwarded_for": xf,
            "client_host": client_host,
            "user_agent": request.headers.get("user-agent") or "",
            "route": str(request.url.path),
        },
    )




@app.get("/api/intake/qr.png")
def intake_qr(intake_id: str = "", token: str = ""):
    from fastapi.responses import Response

    from services.intake.intake import qr_png_for_intake

    if not intake_id or not token:
        raise HTTPException(status_code=400, detail="intake_id and token required")
    png, _link = qr_png_for_intake(intake_id.strip(), token.strip())
    return Response(content=png, media_type="image/png")




@app.get("/api/customer/qr.svg")
def customer_qr_svg(data: str = "", token: str = "", page: str = "continue"):
    from services.customer_friction import generate_qr_png, resolve_continuation

    target = (data or "").strip()
    if not target and token:
        try:
            state = resolve_continuation(token, client="qr")
            if page == "upload":
                target = state.get("upload_url") or ""
            elif page == "intake":
                target = state.get("intake_url") or ""
            else:
                target = state.get("continuation_url") or ""
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid token")
    if not target:
        raise HTTPException(status_code=400, detail="data or token required")
    try:
        png = generate_qr_png(target)
    except Exception as e:
        logging.exception("QR generation failed: %s", e)
        raise HTTPException(status_code=503, detail="QR generation unavailable") from e
    return Response(content=png, media_type="image/png")


@app.get("/api/customer/upload/guidance")
def customer_upload_guidance(project_id: str, token: str = ""):
    from services.customer_friction import analyze_uploads, validate_project_access

    validate_project_id(project_id)
    if token and not validate_project_access(project_id, token):
        raise HTTPException(status_code=403, detail="Invalid token for project")
    return analyze_uploads(project_id)


@app.get("/api/customer/evidence/catalog")
def customer_evidence_catalog():
    from services.customer_friction import list_evidence_catalog

    return list_evidence_catalog()


@app.get("/api/customer/evidence/example/{item_id}")
def customer_evidence_example(item_id: str):
    from services.customer_friction import get_evidence_example

    out = get_evidence_example(item_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail="Not found")
    return out


@app.get("/api/customer/evidence/retrieval/{item_id}")
def customer_evidence_retrieval(item_id: str):
    from services.customer_friction import get_retrieval_help

    out = get_retrieval_help(item_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail="Not found")
    return out


@app.get("/api/customer/evidence/profile")
def customer_evidence_profile(project_id: str, token: str = ""):
    from services.customer_friction import validate_project_access
    from services.evidence_intelligence import get_customer_evidence_profile

    validate_project_id(project_id)
    if not token or not validate_project_access(project_id, token):
        raise HTTPException(status_code=403, detail="Invalid token for project")
    out = get_customer_evidence_profile(project_id)
    try:
        from services.evidence_intelligence.telemetry import emit

        emit("evidence_profile_viewed", project_id=project_id)
    except Exception:
        pass
    return out


@app.post("/api/customer/evidence/confirm")
async def customer_evidence_confirm(
    project_id: str = Body(...),
    token: str = Body(...),
    field: str = Body(...),
    value: str = Body(...),
    action: str = Body(...),
):
    from services.customer_friction import validate_project_access
    from services.evidence_intelligence import confirm_entity

    validate_project_id(project_id)
    if not validate_project_access(project_id, token):
        raise HTTPException(status_code=403, detail="Invalid token for project")
    if action not in ("confirmed", "rejected", "unsure"):
        raise HTTPException(status_code=400, detail="action must be confirmed, rejected, or unsure")
    return confirm_entity(project_id, field=field, value=value, action=action)


# ---------- Chain of Custody / Evidence (with schema validation) ----------
@app.post("/api/coc/event")
async def coc_event(event: dict):
    # Normalize: add defaults so callers don't need to supply crypto fields
    norm = dict(event)
    norm.setdefault("prev_hash", "GENESIS")
    norm.setdefault("hash", "temp")
    # Validate and return friendly errors
    try:
        REGISTRY.validate("event.json", norm)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid event payload: {e}")
    rec = record_event(norm)
    try:
        from services.memory.organism_integration import safe_write_after_coc_event

        safe_write_after_coc_event(norm)
    except Exception:
        pass
    return {"ok": True, "event": rec}
@app.post("/api/evidence/register")
async def evidence_register(
    project_id: str,
    media_type: str,
    owner: str,
    file: UploadFile = File(...),
    token: str = "",
):
    validate_project_id(project_id)
    if token:
        from services.customer_friction import validate_project_access

        if not validate_project_access(project_id, token):
            raise HTTPException(status_code=403, detail="Invalid token for project")
    safe_name = safe_upload_filename(file.filename or "upload.bin")
    if file.size and file.size > 52_428_800:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    pdir = DATA / "projects" / project_id / "evidence"
    pdir.mkdir(parents=True, exist_ok=True)
    dest = pdir / safe_name
    dest.write_bytes(await file.read())
    # quick preview validation (full hash computed inside register_artifact)
    from datetime import datetime as _dt
    from datetime import timezone as _tz
    preview = {
        "artifact_id": f"A-{project_id}",
        "project_id": project_id,
        "path": str(dest),
        "sha256": "0"*64,
        "media_type": media_type,
        "created_utc": _dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "owner": owner
    }
    REGISTRY.validate("artifact.json", preview)
    rec = register_artifact(project_id, dest, media_type, owner)
    from services.acquisition.forensics import safe_record_evidence

    safe_record_evidence(project_id, safe_name, media_type)
    try:
        from services.customer_friction import record_continuation_event

        if token:
            record_continuation_event(
                token,
                "upload_completed",
                step="upload",
                metadata={"filename": safe_name},
            )
    except Exception:
        pass
    intel_message = "We received your files. We are organizing them now."
    try:
        from services.evidence_intelligence import process_evidence_upload

        proc = process_evidence_upload(
            project_id,
            dest,
            artifact_id=rec.get("artifact_id", ""),
            sha256=rec.get("sha256", ""),
            owner=owner,
        )
        intel_message = proc.message
    except Exception:
        pass
    return {"ok": True, "artifact": rec, "intelligence_message": intel_message}

# ---------- Projects / Status Board ----------
@app.get("/api/projects")
def list_projects():
    p = (DATA / "projects")
    items = []
    if p.exists():
        for d in sorted(p.glob("P-*")):
            items.append(d.name)
    return {"ok": True, "projects": items}

@app.get("/api/project/{project_id}/status")
def project_status(project_id: str):
    return {"ok": True, "status": compute_status(project_id)}

@app.post("/api/project/{project_id}/advance")
def project_advance(project_id: str, step_id: str = Body(..., embed=True)):
    st = mark_done(project_id, step_id)
    try:
        from services.memory.organism_integration import safe_write_after_workflow

        safe_write_after_workflow(
            project_id,
            step_id=step_id,
            phase=st.get("phase", ""),
        )
    except Exception:
        pass
    return {"ok": True, "status": st}


@app.get("/api/project/{project_id}/export")
def project_export_binder(project_id: str, request: Request):
    """Operator-only deliverable binder download.

    Wraps services.reports.export_binder() so the control cockpit's
    existing link (ui/control.html) and the operator workflow stop hitting
    a 404. Returns a zip stream with a deterministic Merkle manifest.
    """
    from fastapi.responses import FileResponse

    from services.production import require_ops_access
    from services.reports import export_binder

    require_ops_access(request)
    try:
        zpath = export_binder(project_id.strip())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return FileResponse(
        path=str(zpath),
        filename=zpath.name,
        media_type="application/zip",
    )

# ---------- External cost view ----------
@app.get("/api/project/{project_id}/costs")
def project_costs(project_id: str):
    pdir = DATA / "projects" / project_id
    intake = pdir / "communications" / "intake.json"
    flags = {}
    if intake.exists():
        data = json.loads(intake.read_text())
        flags = data.get("external_flags",{}) or {}
    return {"ok": True, "costs": compute_external_costs(flags)}

# ---------- Vendors ----------
@app.get("/api/vendors")
def list_vendors(category: Optional[str] = None):
    vpath = DATA / "vendors" / "vendors.json"
    items = []
    if vpath.exists():
        items = json.loads(vpath.read_text())
    if category:
        items = [x for x in items if x.get("category")==category]
    return {"ok": True, "vendors": items}

# ---------- RFQ (Request for Quotes) ----------
from services.rfq import create_rfq, list_rfqs, submit_bid, maybe_auto_award  # noqa

@app.post("/api/rfq/create")
def rfq_create(
    project_id: str = Body(...),
    category: str = Body(...),
    title: str = Body(...),
    spec: dict = Body({}),
    invitees: list = Body([]),
    deadline_days: int = Body(7),
    budget_eur: float = Body(10000.0),
    auto_award: bool = Body(True)
):
    return create_rfq(project_id, category, title, spec, invitees, deadline_days, budget_eur, auto_award)

@app.get("/api/rfq/list")
def rfq_list(project_id: str = ""):
    return {"ok": True, "rfqs": list_rfqs(project_id or None)}

@app.post("/api/rfq/submit")
async def rfq_submit(
    token: str = Form(...),
    vendor_name: str = Form(...),
    vendor_email: str = Form(...),
    price_eur: float = Form(...),
    delivery_days: int = Form(...),
    accreditation: str = Form(None),
    notes: str = Form("")
):
    info = parse_intake_token(token)
    rfq_id = info["p"]
    res = submit_bid(rfq_id, vendor_name, vendor_email, float(price_eur), int(delivery_days), bool(accreditation), notes)
    if res.get("ok"):
        maybe_auto_award(rfq_id)
    return res

@app.post("/api/rfq/auto_award")
def rfq_auto_award(rfq_id: str = Body(...)):
    return maybe_auto_award(rfq_id)

# ---------- Manual schema validator ----------
@app.post("/api/schemas/validate")
def validate_schema(kind: str, payload: dict):
    name = "event.json" if kind=="event" else "artifact.json"
    REGISTRY.validate(name, payload)
    return {"ok": True}


@app.post("/api/coc/event/form")
async def coc_event_form(
    project_id: str = Form(...),
    event_type: str = Form(...),
    why: str = Form(""),
    qty: int = Form(1),
    address: str = Form("")
):
    # Build normalized event dict
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ev = {
        "event_id": f"EVT-{project_id}-{int(datetime.now().timestamp())}",
        "event_type": event_type,
        "why": why or "",
        "when_utc": now,
        "who": {"name":"Operator","role":"Manual","email": SETTINGS.smtp_from_email or "ops@keepyourcontracts.com"},
        "where": {"address": address or "Unspecified"},
        "what": [{"id": project_id, "qty": qty}],
        "prev_hash": "GENESIS",
        "hash": "temp"
    }
    # Validate; return clear messages
    try:
        REGISTRY.validate("event.json", ev)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid event payload: {e}")
    rec = record_event(ev)
    try:
        from services.memory import find_entity_id, link_event

        eid = find_entity_id(project_id=project_id)
        if eid:
            link_event(ev["event_id"], eid, project_id)
    except Exception:
        pass
    return {"ok": True, "event": rec}

@app.get("/api/events/recent")
def events_recent(project_id: Optional[str] = None, limit: int = 20):
    # Tail the ledger and return last N events, optionally filtering by project_id
    path = DATA / "ledger" / "ledger.log"
    out = []
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            if not line.strip(): continue
            try:
                rec = json.loads(line)
                if rec.get("kind") != "event": continue
                if project_id:
                    w = rec.get("what") or []
                    pid = (w[0]["id"] if w else "")
                    if pid != project_id: continue
                out.append({
                    "event_id": rec.get("event_id",""),
                    "project_id": (rec.get("what") or [{"id":""}])[0].get("id",""),
                    "event_type": rec.get("event_type",""),
                    "why": rec.get("why",""),
                    "when_utc": rec.get("ts_utc") or rec.get("when_utc",""),
                    "what": rec.get("what",[]),
                    "where": rec.get("where",{})
                })
                if len(out) >= max(1,min(limit,100)): break
            except Exception:
                continue
    return {"ok": True, "events": list(reversed(out))}


# ---------- Central memory (one brain, many vessels) ----------
@app.get("/api/memory/lookup")
def memory_lookup(
    entity_id: str = "",
    email: str = "",
    project_id: str = "",
    lead_id: str = "",
):
    from services.memory.central_memory import lookup

    return {"ok": True, **lookup(entity_id=entity_id, email=email, project_id=project_id, lead_id=lead_id)}


@app.get("/api/memory/self-heal")
def memory_self_heal():
    from services.memory import run_self_healing_scan

    report = run_self_healing_scan(write_suggestions=True)
    return {"ok": True, "report": report}


@app.get("/api/memory/learning")
def memory_learning():
    from services.memory import get_learning_summary

    return {"ok": True, "learning": get_learning_summary()}


@app.get("/api/memory/organism-status")
def memory_organism_status():
    from services.memory.organism_integration import run_integration_audit

    return {"ok": True, **run_integration_audit()}


@app.get("/api/memory/telemetry")
def memory_telemetry(limit: int = 100, subsystem: str = ""):
    from services.memory.telemetry import load_telemetry

    return {
        "ok": True,
        "telemetry": load_telemetry(limit=min(limit, 500), subsystem=subsystem or ""),
    }


@app.get("/api/memory/adaptive-signals")
def memory_adaptive_signals(limit: int = 100):
    from services.memory.adaptive_signals import load_adaptive_signals

    return {"ok": True, "signals": load_adaptive_signals(limit=min(limit, 500))}


@app.get("/api/memory/system-patterns")
def memory_system_patterns():
    from services.memory.organism_observability import get_observability_dashboard

    dash = get_observability_dashboard()
    return {
        "ok": True,
        "patterns": dash.get("learning_patterns", {}),
        "subsystem_health": dash.get("subsystem_health", {}),
        "recommended_improvements": dash.get("recommended_improvements", []),
        "verdict": dash.get("verdict"),
    }


@app.get("/api/memory/observability")
def memory_observability(limit: int = 100):
    from services.memory.organism_observability import get_observability_dashboard

    return {"ok": True, **get_observability_dashboard(telemetry_limit=min(limit, 200))}


# ---------- Operator cockpit + knowledge ----------
@app.get("/api/operator/cockpit")
def operator_cockpit(project_id: str = "", mode: str = ""):
    from services.operator_cockpit import build_cockpit

    return {"ok": True, "cockpit": build_cockpit(project_id=project_id, mode=mode)}


@app.get("/api/operator/guidance")
def operator_guidance(project_id: str = "", mode: str = ""):
    from services.memory.operator_guidance import build_operator_guidance

    return {"ok": True, "guidance": build_operator_guidance(project_id=project_id, mode=mode)}


@app.get("/api/operator/bottlenecks")
def operator_bottlenecks(project_id: str = "", mode: str = ""):
    from services.memory.operator_guidance import get_bottlenecks

    return get_bottlenecks(project_id=project_id, mode=mode)


@app.get("/api/operator/attention")
def operator_attention(project_id: str = "", mode: str = ""):
    from services.memory.operator_guidance import get_attention

    return get_attention(project_id=project_id, mode=mode)


@app.get("/api/operator/learning")
def operator_learning(project_id: str = "", mode: str = "", q: str = ""):
    from services.memory.operator_guidance import get_learning_guidance

    return get_learning_guidance(project_id=project_id, mode=mode, query=q)


@app.get("/api/operator/organism-state")
def operator_organism_state(project_id: str = "", mode: str = ""):
    from services.memory.operator_guidance import get_organism_state_view

    return get_organism_state_view(project_id=project_id, mode=mode)




@app.get("/api/operator/intake/queue")
def operator_intake_queue(request: Request, limit: int = 40):
    from services.intake.queue import get_operator_review_queue
    from services.production import require_ops_access

    require_ops_access(request)
    return get_operator_review_queue(limit=min(max(limit, 1), 100))




@app.get("/api/operator/telemetry-status")
def operator_telemetry_status(request: Request):
    """Operator: actionable telemetry diagnostics for COTE (no fake/synthetic events)."""
    from services.production import require_ops_access
    from services.telemetry_diagnostics import build_telemetry_status

    require_ops_access(request)
    return build_telemetry_status()


@app.get("/api/operator/storage-status")
def operator_storage_status(request: Request):
    """Operator: durable storage + intake upload gate (no secrets)."""
    from services.durable_storage import get_storage_status
    from services.production import require_ops_access

    require_ops_access(request)
    return get_storage_status()


@app.get("/api/operator/intake/diagnostics")
def operator_intake_diagnostics(request: Request):
    """Operator diagnostics — data paths and intake inventory (no secrets)."""
    from services.intake.queue import get_operator_review_queue
    from services.intake.storage import intake_diagnostics
    from services.production import require_ops_access

    require_ops_access(request)
    from services.intake.retention import retention_diagnostics_overlay

    q = get_operator_review_queue(limit=10)
    queue_depth = int(q.get("queue_depth") or 0)
    diag = intake_diagnostics()
    diag.update(retention_diagnostics_overlay(queue_depth=queue_depth))
    from services.intake.inventory import verify_inventory_agreement

    agreement = verify_inventory_agreement(
        inventory=diag.get("inventory"),
        queue_depth=queue_depth,
        retention_scan=diag.get("retention_scan"),
        diagnostics=diag,
    )
    live_scan_status = agreement.get("live_scan_status") or ("healthy" if agreement.get("ok") else "degraded")
    if agreement.get("ok"):
        live_scan_status = "healthy"
    return {
        "ok": agreement.get("ok", True),
        "live_scan_status": live_scan_status,
        "inventory_agreement": agreement,
        "diagnostics": diag,
        "queue_depth": queue_depth,
        "pending_review_count": diag.get("pending_review_count"),
        "queue_rows_generated": q.get("queue_rows_generated"),
        "visibility_warning": q.get("visibility_warning"),
        "newest_intake_id": (q.get("queue") or [{}])[0].get("intake_id") if q.get("queue") else None,
    }




@app.get("/api/operator/intake/reconcile")
def operator_intake_reconcile(request: Request, limit: int = 100):
    from services.intake.reconcile import reconcile_fleet
    from services.production import require_ops_access

    require_ops_access(request)
    return reconcile_fleet(limit=min(max(limit, 1), 500))




@app.get("/api/operator/intake/reconcile/{intake_id}")
def operator_intake_reconcile_intake(request: Request, intake_id: str):
    from services.intake.reconcile import reconcile_intake
    from services.production import require_ops_access

    require_ops_access(request)
    return reconcile_intake(intake_id.strip())


@app.get("/api/operator/intake/raw-disk-scan")
def operator_intake_raw_disk_scan(request: Request, intake_id: str = ""):
    """Live filesystem scan — never cached."""
    from services.intake.proof_gate import live_disk_scan
    from services.production import require_ops_access

    require_ops_access(request)
    iid = intake_id.strip()
    if iid:
        return live_disk_scan(intake_id=iid)
    return live_disk_scan()




@app.get("/api/operator/intake/{intake_id}/files")
def operator_intake_files_list(request: Request, intake_id: str):
    from services.intake.operator_files import list_intake_files_for_operator
    from services.production import require_ops_access

    require_ops_access(request)
    return list_intake_files_for_operator(intake_id.strip())


@app.get("/api/operator/intake/{intake_id}/files/{filename}/download")
def operator_intake_file_download(request: Request, intake_id: str, filename: str):
    from services.intake.operator_files import serve_intake_file
    from services.production import require_ops_access

    require_ops_access(request)
    return serve_intake_file(intake_id.strip(), filename, mode="download")


@app.get("/api/operator/intake/{intake_id}/files/{filename}/view")
def operator_intake_file_view(request: Request, intake_id: str, filename: str):
    from services.intake.operator_files import serve_intake_file
    from services.production import require_ops_access

    require_ops_access(request)
    return serve_intake_file(intake_id.strip(), filename, mode="view")


@app.get("/api/operator/intake/{intake_id}/audit")
def operator_intake_audit(request: Request, intake_id: str):
    from services.intake.retention import get_intake_audit
    from services.production import require_ops_access

    require_ops_access(request)
    return get_intake_audit(intake_id.strip())




@app.get("/api/operator/intake/retention-check/{intake_id}")
def operator_intake_retention_check(request: Request, intake_id: str):
    from services.intake.retention import retention_check
    from services.production import require_ops_access

    require_ops_access(request)
    return retention_check(intake_id.strip())




@app.get("/api/operator/integrity/reconcile")
def operator_integrity_reconcile(request: Request, limit: int = 200):
    from services.intake.forensic_reconcile import run_forensic_reconciliation
    from services.production import require_ops_access

    require_ops_access(request)
    return run_forensic_reconciliation(limit=min(max(limit, 1), 500))


@app.get("/api/operator/integrity/proof")
def operator_integrity_proof(request: Request, limit: int = 500):
    from services.intake.forensic_reconcile import build_integrity_proof
    from services.production import require_ops_access

    require_ops_access(request)
    return build_integrity_proof(limit=min(max(limit, 1), 2000), use_cache=False)


@app.get("/api/operator/integrity/timeline/{intake_id}")
def operator_integrity_timeline(request: Request, intake_id: str):
    from services.intake.custody_timeline import build_custody_timeline
    from services.production import require_ops_access

    require_ops_access(request)
    return build_custody_timeline(intake_id.strip())


@app.post("/api/operator/integrity/recover/{intake_id}")
def operator_integrity_recover(request: Request, intake_id: str):
    from services.intake.forensic_recovery import recover_intake_forensic
    from services.production import require_ops_access

    require_ops_access(request)
    return recover_intake_forensic(intake_id.strip())


@app.post("/api/operator/communications/log")
async def operator_communications_log(request: Request):
    from services.communications.ledger import append_communication
    from services.production import require_ops_access

    require_ops_access(request)
    body = await request.json()
    try:
        rec = append_communication(body, recorded_by=str(body.get("recorded_by") or "operator"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "communication": rec}


@app.get("/api/operator/communications/search")
def operator_communications_search(
    request: Request,
    company_id: str = "",
    company: str = "",
    intake_id: str = "",
    project_id: str = "",
    document_id: str = "",
    delay_event_id: str = "",
    delay_relevance: str = "",
    contact: str = "",
    date_from: str = "",
    date_to: str = "",
    channel: str = "",
    limit: int = 200,
):
    from services.communications.search import search_communications
    from services.production import require_ops_access

    require_ops_access(request)
    return search_communications(
        company_id=company_id,
        company=company,
        intake_id=intake_id,
        project_id=project_id,
        document_id=document_id,
        delay_event_id=delay_event_id,
        delay_relevance=delay_relevance,
        contact=contact,
        date_from=date_from,
        date_to=date_to,
        channel=channel,
        limit=limit,
    )


@app.get("/api/operator/communications/context")
def operator_communications_context(request: Request, intake_id: str = "", reason: str = "", limit: int = 50):
    from services.communications.context import get_contextual_communications
    from services.production import require_ops_access

    require_ops_access(request)
    return get_contextual_communications(intake_id=intake_id.strip(), reason=reason, limit=limit)


@app.get("/api/operator/communications/delay-report/{intake_id}")
def operator_communications_delay_report(request: Request, intake_id: str, project_id: str = ""):
    from services.communications.delay import build_delay_report
    from services.production import require_ops_access

    require_ops_access(request)
    return build_delay_report(intake_id=intake_id.strip(), project_id=project_id.strip())


@app.get("/api/operator/communications/export/forensic")
def operator_communications_export_forensic(
    request: Request,
    intake_id: str = "",
    project_id: str = "",
    company_id: str = "",
    include_delay_report: bool = True,
):
    from services.communications.export import export_communications_forensic
    from services.production import require_ops_access

    require_ops_access(request)
    return export_communications_forensic(
        intake_id=intake_id.strip(),
        project_id=project_id.strip(),
        company_id=company_id.strip(),
        include_delay_report=include_delay_report,
    )


@app.get("/api/operator/communications/{communication_id}")
def operator_communication_get(request: Request, communication_id: str):
    from services.communications.ledger import get_communication
    from services.production import require_ops_access

    require_ops_access(request)
    rec = get_communication(communication_id.strip())
    if not rec:
        raise HTTPException(status_code=404, detail="communication not found")
    return {"ok": True, "communication": rec}


@app.post("/api/operator/intake/action")
async def operator_intake_action(request: Request):
    from services.intake.operator_actions import apply_operator_action
    from services.production import require_ops_access

    require_ops_access(request)
    body = await request.json()
    intake_id = str(body.get("intake_id") or "").strip()
    action = str(body.get("action") or "").strip()
    note = str(body.get("operator_note") or "")
    product_id = str(body.get("product_id") or "").strip()
    if not intake_id:
        raise HTTPException(status_code=400, detail="intake_id required")
    return apply_operator_action(intake_id, action, operator_note=note, product_id=product_id)




@app.get("/api/operator/payment-products")
def operator_payment_products(request: Request):
    """First-sale catalog for operator payment-link workflow."""
    from services.intake.payment_products import list_payment_products
    from services.production import require_ops_access

    require_ops_access(request)
    return {"ok": True, "products": list_payment_products()}


@app.get("/api/cognitive-topology")
def cognitive_topology(request: Request):
    """COTE — lightweight summarized organism topology (no heavy subsystem imports)."""
    from services.cognitive_topology import build_cognitive_topology
    from services.production import require_ops_access

    require_ops_access(request)
    return build_cognitive_topology()


@app.get("/api/operator/customer-friction")
def operator_customer_friction(days: int = 14):
    from services.customer_friction import get_operator_friction_insights

    return get_operator_friction_insights(days=min(max(days, 1), 90))


@app.get("/api/operator/organism-observability")
def operator_organism_observability(request: Request, limit: int = 500):
    from services.runtime_boot import module_pause_response

    paused = module_pause_response("observability")
    if paused is not None:
        return paused
    from services.organism_observability import get_operator_cockpit_observability
    from services.production import require_ops_access

    require_ops_access(request)
    return get_operator_cockpit_observability(telemetry_limit=min(max(limit, 50), 5000))


@app.get("/api/operator/evidence-intelligence")
def operator_evidence_intelligence(project_id: str = ""):
    from services.evidence_intelligence import get_operator_evidence_intelligence

    if not project_id:
        return {"ok": False, "error": "project_id required"}
    validate_project_id(project_id)
    return get_operator_evidence_intelligence(project_id)


@app.get("/api/operator/evidence-intelligence/review-queue")
def operator_evidence_intelligence_review_queue(
    project_id: str = "",
    intake_id: str = "",
    limit: int = 200,
):
    """Append-only EI review queue surface for operators.

    Conflicting extractions, low-confidence entities, and other EI
    events that cannot resolve automatically land here. Accepts either
    `project_id` (legacy) or `intake_id` (current pipeline writes EI
    keyed on intake_id).
    """
    from services.evidence_intelligence import storage as ei_storage

    key = (project_id or intake_id or "").strip()
    if not key:
        return {"ok": False, "error": "project_id or intake_id required"}
    validate_project_id(key)
    try:
        items = ei_storage.load_review_queue(key, limit=int(limit))
    except Exception as exc:
        return {"ok": False, "error": f"queue not readable: {exc}", "items": []}
    return {
        "ok": True,
        "key": key,
        "count": len(items),
        "items": items,
    }


@app.post("/api/operator/evidence-intelligence/reprocess/{intake_id}")
def operator_evidence_intelligence_reprocess(
    request: Request,
    intake_id: str,
    wipe: bool = Body(True, embed=True),
):
    """Operator-triggered EI replay for a single intake.

    Use cases:

    * Recovery — an earlier deploy ran a broken EI loop and persisted
      polluted ``profile.json`` / ``classifications.jsonl`` rows.
      Wiping + replaying rebuilds the on-disk state from the real
      customer uploads.
    * Retroactive feature application — a new EI capability (OCR,
      domain pack, rule changes) has landed and the operator wants to
      apply it to an existing intake.
    * Diagnostics — confirm the live pipeline picks up the same files
      the customer actually uploaded.

    Auth: ``X-Ops-Key`` (write/destructive route).
    Body: ``{"wipe": bool}`` — default ``true``; ``false`` is replay-
    without-wipe (idempotent re-runs are skipped at the existing
    ``_already_processed`` gate inside ``process_evidence_upload``).

    Always returns a structured report. Per-file failures never abort
    the loop and never raise into the HTTP layer.
    """
    from services.production import require_ops_access
    from services.evidence_intelligence import reprocess_intake_evidence

    require_ops_access(request)
    iid = (intake_id or "").strip()
    if not iid:
        return {"ok": False, "error": "intake_id required"}
    validate_project_id(iid)
    return reprocess_intake_evidence(iid, wipe=bool(wipe))


# ── VIO 2.0 — visual awareness interface ──────────────────────────────────────
@app.get("/api/operator/vio/overview")
def vio_overview(request: Request, limit: int = 60):
    """Aggregate all company timelines for VIO 2.0 rendering.

    Returns every active company with its state, timeline segments, and quick
    stats — one API call loads the entire awareness field.
    """
    from services.production import require_ops_access
    from services.vio_overview import build_vio_overview

    require_ops_access(request)
    return build_vio_overview(limit=min(max(limit, 1), 100))


@app.get("/api/operator/vio/company/{intake_id}")
def vio_company_detail(request: Request, intake_id: str):
    """Composite per-company awareness payload for the VIO detail panel.

    Returns every paperwork/evidence/gap/finding signal for one company in a
    single call, so the operator never needs GitHub, Render, logs, or the
    file system to understand a company's state.
    """
    from services.production import require_ops_access
    from services.vio_company_detail import build_company_detail

    require_ops_access(request)
    return build_company_detail(intake_id.strip())


@app.get("/api/operator/organism/state")
def operator_organism_state(request: Request):
    """KYC Aware Organism v0 — self-awareness snapshot.

    Reconciles disk, intake index, queue, VIO, projects, evidence, and beta
    residue. Returns GREEN / AMBER / RED + bottleneck + next action.
    Snapshot is also persisted to {data_root}/organism_state.json and a
    compact row is appended to the snapshot history sidecar.
    """
    from services.organism_state import compute_organism_state, write_organism_state_snapshot
    from services.production import require_ops_access

    require_ops_access(request)
    state = compute_organism_state()
    write_organism_state_snapshot(state)
    return state


@app.get("/api/operator/organism/history")
def operator_organism_history(request: Request, limit: int = 200):
    """KYC Aware Organism v0 — append-only awareness history.

    Returns the most recent organism-state snapshots so operators can
    answer "when did the organism turn AMBER?" or "how did the queue
    depth move over the last hour?" without parsing telemetry.

    The history sidecar is written on every snapshot via
    `write_organism_state_snapshot`. Bounded to the last `limit` rows
    (default 200).
    """
    from services.organism_state import load_organism_state_history
    from services.production import require_ops_access

    require_ops_access(request)
    try:
        rows = load_organism_state_history(limit=max(1, int(limit)))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rows": []}
    return {
        "ok":    True,
        "count": len(rows),
        "rows":  rows,
    }


@app.get("/api/operator/acquisition-intelligence")
def operator_acquisition_intelligence():
    from services.runtime_boot import module_pause_response

    paused = module_pause_response("acquisition")
    if paused is not None:
        return paused
    from services.acquisition.orchestration import get_operator_dashboard

    return get_operator_dashboard()


@app.post("/api/operator/acquisition-intelligence/run")
async def operator_acquisition_intelligence_run(body: dict = Body(default={})):
    import logging

    from services.runtime_blocking import run_blocking

    logger = logging.getLogger(__name__)
    blocked = _safe_mode_block("acquisition")
    if blocked is not None:
        return blocked
    from services.acquisition.orchestration import ingest_public_signal, run_acquisition_cycle

    try:
        if body.get("public_text"):
            return await run_blocking(
                ingest_public_signal,
                text=str(body.get("public_text") or ""),
                source=str(body.get("source") or "operator_manual"),
                source_url=str(body.get("source_url") or ""),
                company_name=str(body.get("company_name") or ""),
                segment=str(body.get("segment") or "compliance-heavy"),
            )
        if body.get("run_live_connector") or body.get("connector") == "usaspending":
            from services.acquisition.connectors.usaspending_live import run_usaspending_live_connector

            return await run_blocking(
                run_usaspending_live_connector,
                queries=body.get("queries"),
                limit_per_query=int(body.get("limit_per_query") or 12),
                campaign_id=str(body.get("campaign_id") or "upload-first"),
                message_variant=str(body.get("message_variant") or "A"),
                min_fit_score=int(body.get("min_fit_score") or 50),
            )
        if body.get("connector") == "reddit" or body.get("run_reddit_connector"):
            from services.acquisition.connectors.reddit import run_reddit_acquisition_cycle

            return await run_blocking(
                run_reddit_acquisition_cycle,
                queries=body.get("queries"),
                subreddits=body.get("subreddits"),
                limit_per_query=int(body.get("limit_per_query") or 8),
                max_posts=int(body.get("max_posts") or 25),
                min_fit_score=int(body.get("min_fit_score") or 50),
                campaign_id=str(body.get("campaign_id") or "reddit-upload-first"),
                message_variant=str(body.get("message_variant") or "A"),
                pause_seconds=float(body.get("pause_seconds") or 0),
            )
        return await run_blocking(
            run_acquisition_cycle,
            run_finder=bool(body.get("run_finder")),
            run_live_connector=bool(body.get("run_live_connector")),
            connector=str(body.get("connector") or "usaspending"),
            campaign_id=str(body.get("campaign_id") or "upload-first"),
            message_variant=str(body.get("message_variant") or "A"),
        )
    except Exception as e:
        logger.exception("acquisition-intelligence/run failed")
        return {
            "ok": False,
            "error_code": "acquisition_runtime_error",
            "error_detail": str(e)[:500],
            "operator_message": f"Acquisition runtime error: {str(e)[:200]}",
        }


@app.post("/api/operator/acquisition-intelligence/approve-lead")
async def operator_acquisition_approve_lead(body: dict = Body(default={})):
    """Operator approves a lead — system generates tracked invite URL and outreach draft."""
    from services.runtime_boot import module_pause_response
    from services.runtime_blocking import run_blocking

    paused = module_pause_response("acquisition")
    if paused is not None:
        return paused
    from services.acquisition.orchestration import approve_and_invite_lead

    lead_id = str(body.get("lead_id") or "").strip()
    if not lead_id:
        return {"ok": False, "error": "lead_id required"}
    return await run_blocking(approve_and_invite_lead, lead_id)


@app.get("/api/operator/operational-alerts")
def operator_operational_alerts():
    from services.alerts import get_operator_dashboard

    return get_operator_dashboard()


@app.post("/api/operator/operational-alerts/acknowledge")
async def operator_operational_alerts_acknowledge(body: dict = Body(default={})):
    from services.alerts.telemetry import acknowledge_alert, link_memory

    alert_id = str(body.get("alert_id") or "").strip()
    if not alert_id:
        return {"ok": False, "detail": "alert_id required"}
    ok = acknowledge_alert(alert_id)
    if ok:
        link_memory("alert_acknowledged", alert_id=alert_id)
    return {"ok": ok}


@app.post("/api/operator/operational-alerts/config")
async def operator_operational_alerts_config(body: dict = Body(default={})):
    from services.alerts import save_config

    allowed = {
        "email_enabled",
        "telegram_enabled",
        "high_fit_threshold",
        "qualification_threshold",
        "abandonment_hours",
        "quiet_hours_start",
        "quiet_hours_end",
        "digest_daily_hour_utc",
        "digest_weekly_hour_utc",
        "min_severity_telegram",
        "min_severity_email",
        "operator_email",
        "operator_name",
        "operator_phone",
    }
    updates = {k: body[k] for k in allowed if k in body}
    return {"ok": True, "config": save_config(updates)}


@app.post("/api/operator/operational-alerts/digest")
async def operator_operational_alerts_digest(body: dict = Body(default={})):
    kind = str(body.get("kind") or "daily").lower()
    if kind == "weekly":
        from services.alerts import generate_weekly_digest

        return generate_weekly_digest()
    from services.alerts import generate_daily_digest

    return generate_daily_digest()


@app.get("/api/operator/reddit-acquisition")
def operator_reddit_acquisition():
    from services.runtime_boot import module_pause_response

    paused = module_pause_response("acquisition")
    if paused is not None:
        return paused
    from services.acquisition.connectors.reddit import get_operator_dashboard

    return get_operator_dashboard()


@app.post("/api/operator/reddit-acquisition/run")
async def operator_reddit_acquisition_run(body: dict = Body(default={})):
    import logging

    from fastapi.responses import JSONResponse

    from services.runtime_blocking import run_blocking

    logger = logging.getLogger(__name__)
    blocked = _safe_mode_block("acquisition")
    if blocked is not None:
        return blocked
    from services.acquisition.connectors.reddit import run_reddit_acquisition_cycle
    broad = bool(body.get("broad") or body.get("broad_discovery"))
    try:
        result = await run_blocking(
            run_reddit_acquisition_cycle,
            queries=body.get("queries"),
            subreddits=body.get("subreddits"),
            limit_per_query=int(body.get("limit_per_query") or 10),
            max_posts=int(body.get("max_posts") or 50),
            min_fit_score=int(body.get("min_fit_score") or 40),
            campaign_id=str(body.get("campaign_id") or "reddit-upload-first"),
            message_variant=str(body.get("message_variant") or "A"),
            pause_seconds=float(body.get("pause_seconds") or 0),
            broad=broad,
        )
        if result.get("ok") is False:
            return JSONResponse(status_code=200, content=result)
        return result
    except Exception as e:
        logger.exception("reddit-acquisition/run failed")
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error_code": "acquisition_runtime_error",
                "error_detail": str(e)[:500],
                "operator_message": f"Acquisition runtime error: {str(e)[:200]}",
            },
        )


@app.post("/api/operator/reddit-acquisition/approve")
async def operator_reddit_acquisition_approve(body: dict = Body(default={})):
    from services.acquisition.connectors.reddit import approve_draft

    post_id = str(body.get("post_id") or "").strip()
    if not post_id:
        return {"ok": False, "detail": "post_id required"}
    return approve_draft(post_id, operator_note=str(body.get("operator_note") or ""))


@app.post("/api/operator/reddit-acquisition/deny")
@app.post("/api/operator/reddit-acquisition/ignore")
async def operator_reddit_acquisition_deny(body: dict = Body(default={})):
    from services.acquisition.connectors.reddit import deny_draft

    post_id = str(body.get("post_id") or "").strip()
    if not post_id:
        return {"ok": False, "detail": "post_id required"}
    return deny_draft(post_id, reason=str(body.get("reason") or "operator_denied"))


@app.get("/api/operator/compliance-intelligence")
def operator_compliance_intelligence():
    from services.compliance_intelligence import get_operator_dashboard

    return get_operator_dashboard()


@app.post("/api/operator/compliance-intelligence/run")
def operator_compliance_intelligence_run(body: dict = Body(default={})):
    from services.compliance_intelligence import run_compliance_intel_cycle

    polling = str(body.get("polling_filter") or "").strip()
    source_ids = body.get("source_ids") or None
    summary = run_compliance_intel_cycle(polling_filter=polling, source_ids=source_ids)
    return {"ok": summary.ok, "summary": summary.model_dump()}


@app.post("/api/operator/compliance-intelligence/review/{change_id}")
def operator_compliance_intelligence_review(change_id: str, body: dict = Body(default={})):
    from services.compliance_intelligence import review_change

    action = str(body.get("action") or "approved").strip()
    note = str(body.get("note") or "").strip()
    return review_change(change_id, action=action, note=note)


@app.get("/api/operator/smtp-status")
def operator_smtp_status():
    from services.production import smtp_env_status

    return {"ok": True, "smtp": smtp_env_status()}


@app.post("/api/operator/test-email")
async def operator_test_email(request: Request, body: dict = Body(...)):
    from services.emails import send_operator_test_email
    from services.production import require_ops_access

    require_ops_access(request)
    to_email = str(body.get("to") or "").strip()
    if not to_email:
        raise HTTPException(status_code=400, detail="to email required")
    result = send_operator_test_email(to_email)
    if result.get("reason") == "smtp_unconfigured":
        return JSONResponse(
            status_code=503,
            content={"ok": False, "detail": "SMTP not configured", "smtp_missing": result},
        )
    if not result.get("ok"):
        return JSONResponse(status_code=502, content={"ok": False, "result": result})
    return {"ok": True, "result": result}


@app.get("/api/knowledge/search")
def knowledge_search(q: str = "", phase: str = "", limit: int = 20):
    from services.knowledge_index import search_knowledge

    return {"ok": True, **search_knowledge(query=q, phase=phase, limit=limit)}


@app.get("/api/knowledge/topic/{topic_id}")
def knowledge_topic(topic_id: str):
    from services.knowledge_index import get_topic

    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Unknown knowledge topic")
    return {"ok": True, "topic": topic}


@app.get("/api/knowledge/catalog")
def knowledge_catalog():
    from services.knowledge_index import knowledge_catalog as catalog

    return {"ok": True, **catalog()}


@app.get("/api/operator/knowledge-cockpit")
def operator_knowledge_cockpit_dashboard():
    from services.knowledge_cockpit import get_dashboard

    return get_dashboard()


@app.get("/api/operator/knowledge-cockpit/search")
def operator_knowledge_cockpit_search(q: str = "", limit: int = 12):
    from services.knowledge_cockpit import search_all

    return search_all(q, limit=limit)


@app.get("/api/operator/knowledge-cockpit/concept/{concept_id}")
def operator_knowledge_cockpit_concept(concept_id: str):
    from services.knowledge_cockpit import explain

    out = explain(concept_id=concept_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail=out.get("detail", "not found"))
    return out


@app.post("/api/operator/knowledge-cockpit/explain")
async def operator_knowledge_cockpit_explain(body: dict = Body(default={})):
    from services.knowledge_cockpit import explain

    text = str(body.get("text") or body.get("query") or "")
    concept_id = str(body.get("concept_id") or "")
    return explain(text=text, concept_id=concept_id)


@app.post("/api/operator/knowledge-cockpit/context")
async def operator_knowledge_cockpit_context(body: dict = Body(default={})):
    from services.knowledge_cockpit.context_retrieval import context_bundle

    return context_bundle(
        acquisition=body.get("acquisition"),
        compliance=body.get("compliance"),
        evidence=body.get("evidence"),
    )


@app.post("/api/operator/knowledge-cockpit/overlay")
async def operator_knowledge_cockpit_overlay(body: dict = Body(default={})):
    from services.runtime_boot import module_pause_response

    paused = module_pause_response("knowledge")
    if paused is not None:
        return paused
    from services.knowledge_cockpit.contextual_overlay import build_overlay
    from services.knowledge_cockpit.telemetry import emit_knowledge_event

    view = str(body.get("view") or "generic")
    payload = body.get("payload")
    if not isinstance(payload, dict):
        payload = {k: v for k, v in body.items() if k != "view"}
    out = build_overlay(view=view, payload=payload)
    emit_knowledge_event(
        "overlay_opened",
        query=view,
        metadata={"view": view, "panel": payload.get("panel")},
    )
    emit_knowledge_event(
        "explanation_generated",
        query=view,
        metadata={"view": view, "explanation_type": view},
    )
    return out


@app.post("/api/operator/knowledge-cockpit/telemetry")
async def operator_knowledge_cockpit_telemetry(request: Request, body: dict = Body(default={})):
    from services.runtime_boot import module_pause_response

    paused = module_pause_response("knowledge")
    if paused is not None:
        return paused
    from services.knowledge_cockpit.telemetry import emit_knowledge_event
    from services.production import require_ops_access

    require_ops_access(request)
    event_type = str(body.get("event_type") or "overlay_collapsed")
    emit_knowledge_event(
        event_type,
        concept_id=str(body.get("concept_id") or ""),
        query=str(body.get("query") or body.get("view") or ""),
        metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
    )
    return {"ok": True, "event_type": event_type}


@app.get("/api/operator/knowledge-cockpit/recent")
def operator_knowledge_cockpit_recent(limit: int = 15):
    from services.knowledge_cockpit.telemetry import get_recent_lookups

    return {"ok": True, "recent": get_recent_lookups(limit=limit)}


@app.get("/api/operator/knowledge-cockpit/graph/{concept_id}")
def operator_knowledge_cockpit_graph(concept_id: str, limit: int = 12):
    from services.knowledge_cockpit.concept_graph import relationship_graph

    return relationship_graph(concept_id, limit=limit)


@app.get("/api/operator/knowledge-cockpit/audit")
def operator_knowledge_cockpit_audit():
    from services.knowledge_cockpit.migration_audit import run_migration_audit

    return run_migration_audit()


# ---------- Ping Host + Test Webhook ----------
from fastapi import Query
import httpx

@app.get("/api/ping-host.json")
def ping_host(host: str = Query(...)):
    try:
        url = f"https://{host}/healthz"
        r = httpx.get(url, timeout=3)
        if r.status_code == 200 and r.json().get("ok") == True:
            return {"host": host, "status": "reachable"}
        return {"host": host, "status": "unreachable"}
    except Exception:
        return {"host": host, "status": "error"}

# ✅ Clean test route for sending test webhooks and email
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

test_router = APIRouter()

@test_router.post("/api/test-webhook")
async def test_webhook(request: Request):
    """Ops-only: exercise kickoff() with a JSON body (same shape as /events/payment/test)."""
    require_ops_access(request)
    try:
        data = await request.json()
        order_id = str(data.get("order_id") or data.get("id") or f"TEST-{int(datetime.now(timezone.utc).timestamp())}")
        email = data.get("email") or ""
        name = data.get("name") or email
        skus = list(data.get("skus") or [])
        if not skus:
            for item in data.get("line_items") or []:
                if isinstance(item, dict):
                    skus.append((item.get("sku") or item.get("title") or "ITEM").strip())
        if not email:
            raise HTTPException(status_code=400, detail="email required")
        if not skus:
            skus = ["TEST-SKU"]
        res = kickoff(order_id, email, name, skus)
        return JSONResponse(content={"received": True, **res})
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("test-webhook kickoff failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

app.include_router(test_router)

       
# ---------- START UVICORN SERVER ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8080
    )


