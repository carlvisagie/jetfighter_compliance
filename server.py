
import logging, json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
try:
    from fastapi import FastAPI
except Exception as e:
    print("FASTAPI import failed:", e)

from fastapi import FastAPI, Request, HTTPException, Form, UploadFile, File, Body
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# --- Services & config ---
from services.config import ROOT, DATA, LOGS, SETTINGS
from services.security import verify_shopify_hmac, make_intake_token, parse_intake_token
from services.adapters.shopify import extract_paid_order
from services.adapters.generic import extract_generic
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

app.include_router(telemetry_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
app.mount("/ui", StaticFiles(directory=str(ROOT / "ui"), html=True), name="ui")

from fastapi.responses import FileResponse

@app.get("/upload")
def upload_page():
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
def _boot_worker():
    try:
        start_worker()
        logging.info("Worker started")
    except Exception as e:
        logging.exception("Worker failed to start: %s", e)

# ---------- Health ----------
@app.get("/healthz")
def health():
    return {"ok": True}

# ---------- Internal helper ----------
def kickoff(order_id: str, email: str, name: str, skus: list):
    meta = new_project(order_id, email, name, skus)
    try:
        init_workflow(meta["project_id"], skus)
        set_phase(meta["project_id"], "INTAKE")
    except Exception as e:
        logging.error(f"Failed to initialize workflow for project {meta['project_id']}: {e}")

    token = make_intake_token(meta["project_id"], email)
    intake_url = f"{SETTINGS.public_base_url}/ui/intake?token={token}"
    html = f"""
    <h2>Welcome to KeepYourContracts</h2>
    <p>Your compliance project <b>{meta['project_id']}</b> is created.</p>
    <p>Please complete intake here: <a href="{intake_url}">{intake_url}</a></p>
    """
    try:
        send_email(email, "Welcome  Your Compliance Project", html)
    except Exception as e:
        logging.warning(f"Email failed to send to {email}: {e}")

    record_event({
        "event_id": f"EVT-{meta['project_id']}-ORDER",
        "event_type": "ATTEST",
        "why": "Order paid; project created",
        "when_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "who": {"name":"System","role":"Automation","email":"noreply@keepyourcontracts.com"},
        "where": {"address":"System"},
        "what": [{"id": meta["project_id"], "qty": 1}],
        "prev_hash": "GENESIS",
        "hash": "temp"
    })
    return {"ok": True, "project_id": meta["project_id"], "intake_url": intake_url}

# ---------- Webhooks / Payment ----------
@app.post("/webhooks/shopify/orders-paid")
async def shopify_orders_paid(request: Request):
    raw = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256","")
    if not verify_shopify_hmac(raw, hmac_header):
        raise HTTPException(status_code=401, detail="Invalid HMAC")
    payload = json.loads(raw.decode("utf-8"))
    order_id, email, name, skus = extract_paid_order(payload)
    if not order_id or not email:
        raise HTTPException(400, "Missing order id or email")
    res = kickoff(order_id, email, name, skus)
    try:
        enqueue("post_payment", {"order_id": order_id, "email": email, "name": name, "skus": skus})
    except Exception as e:
        logging.warning(f"Queue enqueue failed for order {order_id}: {e}")
    return res

@app.post("/events/payment/test")
async def events_payment_test(evt: dict):
    order_id, email, name, skus = extract_generic(evt)
    res = kickoff(order_id, email, name, skus)
    try:
        enqueue("post_payment", {"order_id": order_id, "email": email, "name": name, "skus": skus})
    except Exception as e:
        logging.warning(f"Queue enqueue failed for order {order_id}: {e}")
    return res

# ---------- Intake ----------
@app.get("/ui/intake", response_class=HTMLResponse)
def intake_page():
    return FileResponse(str(ROOT / "ui" / "intake.html"))

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
    ext_translation: str = Form(None)
):
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
            if t.get("id") == "intake_form" or t.get("title", "").lower().startswith("client intake form"):
                t["status"] = "done"
        cl_path.write_text(json.dumps(cl, indent=2))
    except Exception as e:
        logging.warning(f"Failed to update checklist for project {project_id}: {e}")

    return {"ok": True, "project_id": project_id}

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
    return {"ok": True, "event": rec}
@app.post("/api/evidence/register")
async def evidence_register(project_id: str, media_type: str, owner: str, file: UploadFile = File(...)):
    pdir = DATA / "projects" / project_id / "evidence"
    pdir.mkdir(parents=True, exist_ok=True)
    dest = pdir / file.filename
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
    return {"ok": True, "artifact": rec}

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
    return {"ok": True, "status": st}

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
    try:
        data = await request.json()
        print("✅ Webhook Received:", data)

        subject = f"✅ TEST Order: {data.get('id', 'N/A')}"
        items = data.get("line_items", [])
        if not isinstance(items, list):
            print("⚠️ line_items is not a list:", items)
            items = []

        body = f"Email: {data.get('email', 'none')}\nLine Items:\n"
        for item in items:
            body += f"  – {item.get('title', 'N/A')} (SKU: {item.get('sku', 'N/A')})\n"

        from services.emails import send_email
        send_email(to_email=data.get("email", "fallback@example.com"), subject=subject, html_body=body)

        return JSONResponse(content={"received": True, "data": data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

       
# ---------- START UVICORN SERVER ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8080
    )




from fastapi.responses import FileResponse

@app.get("/upload")
def upload_page():
    return FileResponse(ROOT / "ui" / "upload.html")

