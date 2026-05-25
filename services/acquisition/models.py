"""Lead model and allowed segments/statuses for acquisition discovery."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SEGMENTS = (
    "aerospace",
    "manufacturing",
    "compliance-heavy",
    "audit-stressed",
    "government-subcontractor",
    "quality-ops-manager",
)

SEGMENT_ALIASES = {
    "aerospace suppliers": "aerospace",
    "aerospace supplier": "aerospace",
    "aero": "aerospace",
    "manufacturing operators": "manufacturing",
    "manufacturing": "manufacturing",
    "mfg": "manufacturing",
    "compliance-heavy smbs": "compliance-heavy",
    "compliance-heavy": "compliance-heavy",
    "compliance heavy": "compliance-heavy",
    "audit-stressed": "audit-stressed",
    "audit stressed": "audit-stressed",
    "audit/documentation stressed": "audit-stressed",
    "government subcontractors": "government-subcontractor",
    "government subcontractor": "government-subcontractor",
    "govcon": "government-subcontractor",
    "gov contractor": "government-subcontractor",
    "quality managers": "quality-ops-manager",
    "operations managers": "quality-ops-manager",
    "quality-ops-manager": "quality-ops-manager",
    "quality / operations": "quality-ops-manager",
}

IMPORT_COLUMNS = (
    "company_name",
    "website",
    "contact_name",
    "contact_title",
    "contact_email",
    "linkedin_url",
    "industry",
    "segment",
    "source",
    "source_url",
    "location",
    "notes",
)

LEAD_STATUSES = (
    "new",
    "reviewed",
    "approved_for_outreach",
    "contacted",
    "responded",
    "inquiry_submitted",
    "intake_completed",
    "rejected",
    "do_not_contact",
)

LeadStatus = str  # literal union for simplicity in MVP


@dataclass
class ImportStats:
    total_rows: int = 0
    valid_rows: int = 0
    rejected_rows: int = 0
    duplicates_skipped: int = 0
    imported: int = 0
    scored_80_plus: int = 0
    scored_65_79: int = 0
    low_fit: int = 0
    rejection_reasons: List[str] = field(default_factory=list)
    top_pain_signals: Dict[str, int] = field(default_factory=dict)
    new_lead_ids: List[str] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_segment(raw: str) -> Optional[str]:
    key = (raw or "").strip().lower()
    if not key:
        return None
    if key in SEGMENTS:
        return key
    return SEGMENT_ALIASES.get(key)


@dataclass
class Lead:
    lead_id: str
    company_name: str
    website: str = ""
    contact_name: str = ""
    contact_title: str = ""
    contact_email: str = ""
    linkedin_url: str = ""
    industry: str = ""
    segment: str = ""
    source: str = ""
    source_url: str = ""
    location: str = ""
    pain_signals: List[str] = field(default_factory=list)
    compliance_signals: List[str] = field(default_factory=list)
    fit_score: int = 0
    confidence_score: int = 0
    notes: str = ""
    status: str = "new"
    created_utc: str = field(default_factory=utc_now)
    updated_utc: str = field(default_factory=utc_now)
    reason_summary: str = ""
    inquiry_routed_link: str = ""
    ability_to_pay_score: int = 0
    urgency_score: int = 0
    compliance_pain_score: int = 0
    operational_complexity_score: int = 0
    trust_readiness_score: int = 0
    acquisition_priority_score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["pain_signals"] = list(self.pain_signals)
        d["compliance_signals"] = list(self.compliance_signals)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lead":
        pain = data.get("pain_signals") or []
        comp = data.get("compliance_signals") or []
        if isinstance(pain, str):
            pain = [p.strip() for p in pain.split(";") if p.strip()]
        if isinstance(comp, str):
            comp = [p.strip() for p in comp.split(";") if p.strip()]
        return cls(
            lead_id=str(data.get("lead_id", "")),
            company_name=str(data.get("company_name", "")),
            website=str(data.get("website", "")),
            contact_name=str(data.get("contact_name", "")),
            contact_title=str(data.get("contact_title", "")),
            contact_email=str(data.get("contact_email", "")),
            linkedin_url=str(data.get("linkedin_url", "")),
            industry=str(data.get("industry", "")),
            segment=str(data.get("segment", "")),
            source=str(data.get("source", "")),
            source_url=str(data.get("source_url", "")),
            location=str(data.get("location", "")),
            pain_signals=list(pain),
            compliance_signals=list(comp),
            fit_score=int(data.get("fit_score") or 0),
            confidence_score=int(data.get("confidence_score") or 0),
            notes=str(data.get("notes", "")),
            status=str(data.get("status") or "new"),
            created_utc=str(data.get("created_utc") or utc_now()),
            updated_utc=str(data.get("updated_utc") or utc_now()),
            reason_summary=str(data.get("reason_summary", "")),
            inquiry_routed_link=str(data.get("inquiry_routed_link", "")),
            ability_to_pay_score=int(data.get("ability_to_pay_score") or 0),
            urgency_score=int(data.get("urgency_score") or 0),
            compliance_pain_score=int(data.get("compliance_pain_score") or 0),
            operational_complexity_score=int(data.get("operational_complexity_score") or 0),
            trust_readiness_score=int(data.get("trust_readiness_score") or 0),
            acquisition_priority_score=int(data.get("acquisition_priority_score") or 0),
        )
