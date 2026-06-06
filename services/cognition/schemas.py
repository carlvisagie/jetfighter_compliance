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


class CognitionSummary(BaseModel):
    timestamp_utc: str
    state: AwarenessState
    memory: MemoryReasoning
    gap_resolutions: List[GapResolution] = Field(default_factory=list)
    generated_documents: List[GeneratedDocument] = Field(default_factory=list)
    next_actions: List[NextAction] = Field(default_factory=list)
    drafts: List[CustomerDraft] = Field(default_factory=list)
