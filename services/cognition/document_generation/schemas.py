from __future__ import annotations
from typing import List

from pydantic import BaseModel, Field, model_validator


class ProvenanceTrace(BaseModel):
    source_file: str
    source_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class GeneratedDocument(BaseModel):
    doc_id: str
    doc_type: str
    title: str
    content_markdown: str
    is_partial: bool
    unresolved_fields: List[str] = Field(default_factory=list)
    provenance: List[ProvenanceTrace] = Field(default_factory=list)

    @model_validator(mode='after')
    def enforce_rules(self):
        # PARTIAL documents must list unresolved_fields
        if self.is_partial and not self.unresolved_fields:
            raise ValueError("PARTIAL documents must list unresolved_fields")
        
        # GENERATED documents must have provenance. No unsupported facts allowed.
        if not self.provenance:
            raise ValueError("GENERATED documents must have provenance")
            
        return self
