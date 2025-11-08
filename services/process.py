from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
from .config import DATA
from .checklist import build_checklist

WF_DIR = DATA / "process"
WF_DIR.mkdir(parents=True, exist_ok=True)

# Canonical step library: id, title, required, sla_minutes, opens_on
STEP_LIB = {
    "order_ack": {"title":"Order acknowledged","required": True, "sla_minutes": 60,  "opens_on":"ORDER"},
    "intake_received": {"title":"Client intake form received","required": True, "sla_minutes": 1440, "opens_on":"ORDER"},
    "scope_locked": {"title":"Scope locked with client","required": True, "sla_minutes": 2880, "opens_on":"INTAKE"},
    "evidence_binder_ready": {"title":"Evidence binder ready","required": True, "sla_minutes": 7*1440, "opens_on":"SCOPE"},
    "handover_signed": {"title":"Handover signed","required": True, "sla_minutes": 8*1440, "opens_on":"BINDER"},
    # Extras per SKU (CMMC/DPP)
    "cmmc_gap": {"title":"CMMC gap assessment complete","required": True, "sla_minutes": 2880, "opens_on":"SCOPE"},
    "dpp_model": {"title":"DPP data model built","required": True, "sla_minutes": 2880, "opens_on":"SCOPE"}
}

SKU_TO_STEPS = {
    "CMMC-L1": ["order_ack","intake_received","scope_locked","cmmc_gap","evidence_binder_ready","handover_signed"],
    "CMMC-L2": ["order_ack","intake_received","scope_locked","cmmc_gap","evidence_binder_ready","handover_signed"],
    "DPP-ESPR": ["order_ack","intake_received","scope_locked","dpp_model","evidence_binder_ready","handover_signed"],
}

def _utcnow():
    return datetime.now(timezone.utc)

def _ts():
    return _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def init_workflow(project_id: str, skus: List[str]) -> Dict:
    # Build steps list (dedup, preserve order by SKU declaration)
    seen, steps = set(), []
    for sku in skus:
        for sid in SKU_TO_STEPS.get(sku, ["order_ack","intake_received","scope_locked","evidence_binder_ready","handover_signed"]):
            if sid not in seen:
                seen.add(sid); steps.append({"id": sid, "title": STEP_LIB[sid]["title"], "required": STEP_LIB[sid]["required"], "status":"todo",
                                             "opened_on":"ORDER" if STEP_LIB[sid]["opens_on"]=="ORDER" else "PENDING",
                                             "created_utc": _ts(), "done_utc": "", "due_utc": ""})
    wf = {"project_id": project_id, "skus": skus, "created_utc": _ts(), "phase":"ORDER"}
    _save(project_id, {"workflow": wf, "steps": steps})
    # Precompute due for steps that open on ORDER
    recalc_due(project_id)
    return _load(project_id)

def _wf_path(project_id: str) -> Path:
    return WF_DIR / f"{project_id}.json"

def _load(project_id: str) -> Dict:
    p = _wf_path(project_id)
    return json.loads(p.read_text()) if p.exists() else {"workflow":{}, "steps":[]}

def _save(project_id: str, obj: Dict):
    _wf_path(project_id).write_text(json.dumps(obj, indent=2))

def set_phase(project_id: str, phase: str):
    obj = _load(project_id); obj["workflow"]["phase"] = phase; _save(project_id, obj); recalc_due(project_id)

def mark_done(project_id: str, step_id: str):
    obj = _load(project_id)
    found = False
    for s in obj["steps"]:
        if s["id"] == step_id:
            s["status"] = "done"; s["done_utc"] = _ts(); found = True
    if not found: raise ValueError(f"step {step_id} not found")
    _save(project_id, obj); return compute_status(project_id)

def recalc_due(project_id: str):
    obj = _load(project_id)
    phase = obj["workflow"].get("phase","ORDER")
    now = _utcnow()
    for s in obj["steps"]:
        if s["status"] == "done": continue
        opens_on = STEP_LIB[s["id"]]["opens_on"]
        if s["opened_on"] == "PENDING" and ((opens_on=="ORDER" and phase in ["ORDER","INTAKE","SCOPE","BINDER","HANDOVER"]) or
                                            (opens_on=="INTAKE" and phase in ["INTAKE","SCOPE","BINDER","HANDOVER"]) or
                                            (opens_on=="SCOPE" and phase in ["SCOPE","BINDER","HANDOVER"]) or
                                            (opens_on=="BINDER" and phase in ["BINDER","HANDOVER"])):
            s["opened_on"] = phase
            s["due_utc"] = (_utcnow() + timedelta(minutes=STEP_LIB[s["id"]]["sla_minutes"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    _save(project_id, obj)

def compute_status(project_id: str) -> Dict:
    recalc_due(project_id)
    obj = _load(project_id)
    steps = obj["steps"]
    total = len(steps)
    done = sum(1 for s in steps if s["status"]=="done")
    required_open = [s for s in steps if s["required"] and s["status"]!="done" and s["opened_on"]!="PENDING"]
    overdue = [s for s in required_open if s.get("due_utc") and s["due_utc"] < _ts()]
    rag = "green" if len(required_open)==0 else ("red" if len(overdue)>0 else "amber")
    return {"project_id": project_id, "phase": obj["workflow"].get("phase","ORDER"),
            "counts":{"total":total,"done":done,"open":total-done,"required_open":len(required_open),"overdue":len(overdue)},
            "rag": rag, "steps": steps}
