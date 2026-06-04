"""Pydantic models for evidence intelligence (v1 rule-based)."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

EntityStatus = Literal["inferred", "confirmed", "rejected", "conflicting", "unsure"]
DocumentType = Literal[
    "policy",
    "procedure",
    "screenshot",
    "training_record",
    "asset_inventory",
    "vulnerability_report",
    "system_diagram",
    "vendor_document",
    "invoice_or_receipt",
    "ssp",
    "poam",
    "contract",
    "access_control_evidence",
    "mfa_evidence",
    "backup_evidence",
    "incident_response",
    "unknown",
]

GapPriority = Literal["high", "medium", "low"]


class ExtractionResult(BaseModel):
    ok: bool = True
    source_file: str = ""
    mime_hint: str = ""
    text_length: int = 0
    text_preview: str = ""
    extraction_method: str = "none"
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    pending_analysis: bool = False
    ocr_applied: bool = False
    ocr_status: str = ""
    ocr_text_length: int = 0
    ocr_pages: int = 0


class ExtractedItem(BaseModel):
    value: str
    type: str
    confidence: float = 0.5
    source_file: str = ""
    extraction_method: str = "rules"
    evidence_span: str = ""
    created_utc: str = ""
    status: EntityStatus = "inferred"


class ClassificationResult(BaseModel):
    document_type: DocumentType = "unknown"
    confidence: float = 0.0
    source_file: str = ""
    signals: List[str] = Field(default_factory=list)


class GapItem(BaseModel):
    gap_id: str
    label: str
    plain: str
    why: str = ""
    priority: GapPriority = "medium"
    confidence: float = 0.5
    example_item_id: str = ""
    source_files: List[str] = Field(default_factory=list)


class ProjectProfile(BaseModel):
    project_id: str
    updated_utc: str = ""
    company_name_candidates: List[ExtractedItem] = Field(default_factory=list)
    emails: List[ExtractedItem] = Field(default_factory=list)
    phones: List[ExtractedItem] = Field(default_factory=list)
    addresses: List[ExtractedItem] = Field(default_factory=list)
    domains: List[ExtractedItem] = Field(default_factory=list)
    websites: List[ExtractedItem] = Field(default_factory=list)
    people: List[ExtractedItem] = Field(default_factory=list)
    vendors: List[ExtractedItem] = Field(default_factory=list)
    technologies: List[ExtractedItem] = Field(default_factory=list)
    cloud_providers: List[ExtractedItem] = Field(default_factory=list)
    identity_providers: List[ExtractedItem] = Field(default_factory=list)
    compliance_references: List[ExtractedItem] = Field(default_factory=list)
    document_inventory: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_coverage: Dict[str, bool] = Field(default_factory=dict)
    unknowns_needing_confirmation: List[str] = Field(default_factory=list)


class ProcessingResult(BaseModel):
    ok: bool = True
    project_id: str = ""
    source_file: str = ""
    status: Literal["completed", "pending_analysis", "failed", "skipped"] = "completed"
    message: str = "We received your files. We are organizing them now."
    extraction: Optional[ExtractionResult] = None
    classification: Optional[ClassificationResult] = None
    entities_extracted: int = 0
    gaps_detected: int = 0
    profile_updated: bool = False
