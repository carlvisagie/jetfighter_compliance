from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid

router = APIRouter()

BASE_DIR = Path("data/telemetry")
DAILY_DIR = BASE_DIR / "daily"

DAILY_DIR.mkdir(parents=True, exist_ok=True)

class TelemetryEvent(BaseModel):

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    event_type: str

    occurred_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    session_id: Optional[str] = None
    visitor_id: Optional[str] = None
    lead_id: Optional[str] = None

    page_url: Optional[str] = None
    referrer: Optional[str] = None

    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None

    user_agent: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None

    screen_width: Optional[int] = None
    screen_height: Optional[int] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)

def append_event(event: dict):

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    file_path = DAILY_DIR / f"{date_str}.jsonl"

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "`n")

@router.post("/api/telemetry/event")
async def ingest_telemetry(event: TelemetryEvent):

    payload = event.model_dump()

    append_event(payload)

    return {
        "ok": True,
        "stored": True,
        "event_id": payload["event_id"],
        "event_type": payload["event_type"]
    }
