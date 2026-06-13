from __future__ import annotations
import json, uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from .config import DATA, SETTINGS
from .emails import send_email
from .security import make_intake_token  # reuse signer
from .ledger import record_event


def _send_rfq_email(to: str, subject: str, html: str) -> None:
    """Send via modern email_service adapter (Resend → SMTP → manual fallback)."""
    try:
        from .communications.email_service import send_raw
        send_raw(to=to, subject=subject, html=html)
    except Exception:
        # Graceful fallback to legacy adapter — logs warning internally
        try:
            send_email(to, subject, html)
        except Exception:
            pass

RFQ_DIR = DATA / "rfq"
RFQ_DIR.mkdir(parents=True, exist_ok=True)

def _now() -> str: return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _deadline(days:int) -> str: return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass
class Bid:
    bid_id: str
    vendor_name: str
    vendor_email: str
    price_eur: float
    delivery_days: int
    accreditation: bool = False
    notes: str = ""
    submitted_utc: str = ""

@dataclass
class RFQ:
    rfq_id: str
    project_id: str
    category: str
    title: str
    spec: Dict
    invitees: List[Dict]  # {name, email, url?}
    deadline_utc: str
    budget_eur: float
    auto_award: bool
    status: str = "open"  # open | awarded | canceled | expired
    created_utc: str = ""
    bids: List[Bid] = None
    award_bid_id: Optional[str] = None

def _rfq_path(rfq_id:str) -> Path: return RFQ_DIR / f"{rfq_id}.json"

def save_rfq(obj: RFQ):
    d = asdict(obj)
    d["bids"] = [asdict(b) for b in (obj.bids or [])]
    safe_write_json(_rfq_path(obj.rfq_id), d, component="rfq", context=f"rfq {obj.rfq_id}", severity="critical")

    # Emit telemetry so organism knows RFQ state changed
    try:
        from services.memory.telemetry import emit_telemetry
        emit_telemetry(
            "rfq",
            "rfq_saved",
            metadata={
                "rfq_id": obj.rfq_id,
                "project_id": obj.project_id,
                "status": obj.status,
                "bids_count": len(obj.bids or [])
            }
        )
    except Exception:
        pass

def load_rfq(rfq_id: str) -> RFQ:
    d = json.loads(_rfq_path(rfq_id).read_text())
    rfq = RFQ(**{k:v for k,v in d.items() if k not in ("bids",)})
    rfq.bids = [Bid(**b) for b in d.get("bids",[])]
    return rfq

def list_rfqs(project_id: Optional[str]=None) -> List[Dict]:
    out=[]
    for p in RFQ_DIR.glob("*.json"):
        d = json.loads(p.read_text()); 
        if project_id and d.get("project_id")!=project_id: continue
        out.append({"rfq_id":d["rfq_id"],"project_id":d["project_id"],"category":d["category"],"status":d["status"],"deadline_utc":d["deadline_utc"],"bids":len(d.get("bids",[]))})
    return sorted(out, key=lambda x:x["rfq_id"], reverse=True)

def create_rfq(project_id:str, category:str, title:str, spec:Dict, invitees:List[Dict], deadline_days:int, budget_eur:float, auto_award:bool)->Dict:
    rfq = RFQ(
        rfq_id=f"RFQ-{uuid.uuid4().hex[:8].upper()}",
        project_id=project_id, category=category, title=title, spec=spec,
        invitees=invitees, deadline_utc=_deadline(deadline_days),
        budget_eur=budget_eur, auto_award=auto_award,
        created_utc=_now(), bids=[]
    )
    save_rfq(rfq)
    record_event({"event_id": f"{rfq.rfq_id}-OPEN","event_type":"ATTEST","why":f"RFQ opened for {category}",
                  "when_utc": _now(),"who":{"name":"System","role":"Automation","email":"noreply@keepyourcontracts.com"},
                  "where":{"address":"System"},"what":[{"id": project_id, "qty":1}]})
    try:
        from services.memory.organism_integration import safe_write_after_rfq

        safe_write_after_rfq(rfq.rfq_id, project_id, event_kind="rfq_opened", category=category)
    except Exception:
        pass
    # send invites via modern email adapter (Resend → SMTP → manual fallback)
    for v in invitees:
        token = make_intake_token(rfq.rfq_id, v.get("email",""))
        link = f"{SETTINGS.public_base_url}/ui/vendor_quote.html?token={token}"
        if v.get("email"):
            _send_rfq_email(
                v["email"],
                f"RFQ: {title}",
                f"<p>You are invited to quote for <b>{title}</b>.</p><p>Submit here: <a href='{link}'>{link}</a></p>",
            )
    return {"ok": True, "rfq_id": rfq.rfq_id}

def score_bid(b: Bid, w_sla:float, w_acc:float) -> float:
    # Higher is better. Price dominates (inverse), then SLA, then accreditation bonus.
    base = 1000.0 / max(b.price_eur, 0.01)
    sla = w_sla * (30.0 / max(b.delivery_days,1))
    acc = w_acc * (1.0 if b.accreditation else 0.0)
    return base + sla + acc

def submit_bid(rfq_id:str, vendor_name:str, vendor_email:str, price_eur:float, delivery_days:int, accreditation:bool, notes:str)->Dict:
    rfq = load_rfq(rfq_id)
    if rfq.status != "open": return {"ok": False, "error":"RFQ not open"}
    bid = Bid(bid_id=f"B-{uuid.uuid4().hex[:6].upper()}", vendor_name=vendor_name, vendor_email=vendor_email,
              price_eur=price_eur, delivery_days=delivery_days, accreditation=accreditation, notes=notes, submitted_utc=_now())
    rfq.bids.append(bid); save_rfq(rfq)
    record_event({"event_id": f"{rfq.rfq_id}-{bid.bid_id}","event_type":"ATTEST","why":"RFQ bid submitted",
                  "when_utc": _now(),"who":{"name":vendor_name,"role":"Vendor","email":vendor_email},
                  "where":{"address":"Vendor Portal"},"what":[{"id": rfq.project_id,"qty":1}]})
    try:
        from services.memory.organism_integration import safe_write_after_rfq

        safe_write_after_rfq(rfq.rfq_id, rfq.project_id, event_kind="rfq_bid", category=rfq.category)
    except Exception:
        pass
    return {"ok": True, "bid_id": bid.bid_id}

def maybe_auto_award(rfq_id:str)->Dict:
    rfq = load_rfq(rfq_id)
    # Expire if past deadline
    if rfq.status=="open" and rfq.deadline_utc < _now():
        rfq.status = "expired"; save_rfq(rfq); return {"ok": True, "status":"expired"}
    if not rfq.auto_award or rfq.status!="open": return {"ok": True, "status": rfq.status}
    if len(rfq.bids) < 2: return {"ok": True, "status":"waiting_min_bids"}
    # select best within budget
    w_sla = float(getattr(SETTINGS, "rfq_weight_sla", 0.3))
    w_acc = float(getattr(SETTINGS, "rfq_weight_accredit", 0.2))
    candidates = [b for b in rfq.bids if b.price_eur <= rfq.budget_eur]
    if not candidates: return {"ok": True, "status":"over_budget"}
    best = max(candidates, key=lambda b: score_bid(b, w_sla, w_acc))
    rfq.status = "awarded"; rfq.award_bid_id = best.bid_id; save_rfq(rfq)
    # Notify winner via modern email adapter (Resend → SMTP → manual fallback)
    _send_rfq_email(
        best.vendor_email,
        f"AWARD: {rfq.title}",
        "<p>Congratulations, your bid is awarded.</p>",
    )
    record_event({"event_id": f"{rfq.rfq_id}-AWARD","event_type":"ATTEST","why":f"Awarded to {best.vendor_name}",
                  "when_utc": _now(),"who":{"name":"System","role":"Automation","email":"noreply@keepyourcontracts.com"},
                  "where":{"address":"System"},"what":[{"id": rfq.project_id,"qty":1}]})
    try:
        from services.memory.organism_integration import safe_write_after_rfq

        safe_write_after_rfq(rfq.rfq_id, rfq.project_id, event_kind="rfq_awarded", category=rfq.category)
    except Exception:
        pass
    return {"ok": True, "status":"awarded", "bid_id": best.bid_id}
