from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator

from .document_generation.schemas import GeneratedDocument


class ResolutionStrategy(str, Enum):
    GENERATE = "generate"
    PARTIAL = "partial"
    REQUEST = "request"


class GapResolution(BaseModel):
    gap_id: str
    strategy: ResolutionStrategy
    confidence: float = Field(..., ge=0.0, le=1.0)
    target_document_type: str
    missing_fields: List[str] = Field(default_factory=list)
    reasoning: str
    evidence_used: List[str] = Field(default_factory=list)
    reason_unresolved: str = ""

    @model_validator(mode='after')
    def enforce_rules(self):
        if self.strategy == ResolutionStrategy.REQUEST:
            if not self.reasoning or not self.reasoning.strip():
                raise ValueError("REQUEST items must explain why the information cannot be inferred")
        elif self.strategy == ResolutionStrategy.PARTIAL:
            if not self.missing_fields:
                raise ValueError("PARTIAL strategy must list missing_fields")
        return self


class AwarenessState(BaseModel):
    knows: List[str] = Field(default_factory=list)
    does_not_know: List[str] = Field(default_factory=list)
    contradictions: List[Dict[str, Any]] = Field(default_factory=list)
    stale_info: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_level: float = Field(..., ge=0.0, le=1.0)


class MemoryReasoning(BaseModel):
    trajectory: str
    changed_since_last_run: List[str] = Field(default_factory=list)


class NextAction(BaseModel):
    action_id: str
    title: str
    description: str
    assignee: str
    priority_score: float = Field(..., ge=0.0, le=100.0)
    risk_type: str


class CustomerDraft(BaseModel):
    subject: str
    body_html: str
    ready_to_send: bool = False


class ValidationFact(BaseModel):
    fact: str
    source: str

class ValidationInference(BaseModel):
    inference: str
    confidence: float
    basis: List[str]

class ValidationGeneration(BaseModel):
    document_type: str
    source_evidence: List[str]
    inferred_facts: List[str]
    unresolved_fields: List[str]
    confidence_score: float

class ValidationAssumption(BaseModel):
    assumption: str
    reason: str

class ValidationRequest(BaseModel):
    gap_id: str
    reason_not_inferred: str
    reason_not_generated: str
    exact_evidence_required: str

class ValidationHumanReview(BaseModel):
    item_type: str
    item_id: str
    reason: str
    confidence: float

class ValidationReport(BaseModel):
    project_id: str
    timestamp_utc: str
    facts_used: List[ValidationFact] = Field(default_factory=list)
    inferences_made: List[ValidationInference] = Field(default_factory=list)
    documents_generated: List[ValidationGeneration] = Field(default_factory=list)
    assumptions: List[ValidationAssumption] = Field(default_factory=list)
    requests: List[ValidationRequest] = Field(default_factory=list)
    human_review_items: List[ValidationHumanReview] = Field(default_factory=list)
    confidence_summary: float
    safety_warnings: List[str] = Field(default_factory=list)

class CognitionSummary(BaseModel):
    timestamp_utc: str
    state: AwarenessState
    memory: MemoryReasoning
    gap_resolutions: List[GapResolution] = Field(default_factory=list)
    generated_documents: List[GeneratedDocument] = Field(default_factory=list)
    next_actions: List[NextAction] = Field(default_factory=list)
    drafts: List[CustomerDraft] = Field(default_factory=list)

class CognitionMetrics(BaseModel):
    workload_elimination_percentage: float = 0.0
    documents_generated: List[str] = Field(default_factory=list)
    documents_requested: List[str] = Field(default_factory=list)
    questions_avoided: List[str] = Field(default_factory=list)
    questions_asked: List[str] = Field(default_factory=list)
    estimated_hours_saved: float = 0.0
    confidence_score: float = 0.0
    inference_count: int = 0
    generation_count: int = 0
    request_count: int = 0

