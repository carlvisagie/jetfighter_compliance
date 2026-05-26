"""Pydantic models for continuous compliance intelligence."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

AuthorityLevel = Literal["primary", "secondary", "reference"]
PollFrequency = Literal["daily", "weekly", "monthly"]
ChangeType = Literal["new_page", "changed_content", "removed_content", "title_change", "phrase_change", "unchanged"]
Severity = Literal["info", "low", "medium", "high", "critical"]
ReviewStatus = Literal["pending", "approved", "dismissed", "deferred"]


class SourceRecord(BaseModel):
    source_id: str
    name: str
    url: str
    authority_level: AuthorityLevel = "primary"
    topic_tags: List[str] = Field(default_factory=list)
    polling_frequency: PollFrequency = "weekly"
    enabled: bool = True
    etag: str = ""
    last_modified: str = ""
    content_hash: str = ""
    last_seen_utc: str = ""
    last_changed_utc: str = ""
    last_status_code: int = 0
    last_error: str = ""
    user_agent: str = "KeepYourContracts-ComplianceIntel/1.0"


class FetchResult(BaseModel):
    source_id: str
    ok: bool = True
    status_code: int = 0
    fetched_at_utc: str = ""
    sha256: str = ""
    content_length: int = 0
    excerpt: str = ""
    snapshot_path: str = ""
    etag: str = ""
    last_modified: str = ""
    not_modified: bool = False
    error: str = ""


class ChangeRecord(BaseModel):
    change_id: str
    source_id: str
    change_type: ChangeType
    old_hash: str = ""
    new_hash: str = ""
    diff_summary: str = ""
    confidence: float = 0.8
    detected_at_utc: str = ""
    title_old: str = ""
    title_new: str = ""


class ClassificationResult(BaseModel):
    change_id: str
    frameworks: List[str] = Field(default_factory=list)
    impact_areas: List[str] = Field(default_factory=list)
    severity: Severity = "info"
    urgent: bool = False
    summary: str = ""
    confidence: float = 0.75


class ImpactRecord(BaseModel):
    impact_id: str
    change_id: str
    source_id: str
    severity: Severity = "info"
    affected_services: List[str] = Field(default_factory=list)
    affected_topics: List[str] = Field(default_factory=list)
    affected_project_patterns: List[str] = Field(default_factory=list)
    evidence_guidance_notes: List[str] = Field(default_factory=list)
    operator_actions: List[str] = Field(default_factory=list)
    knowledge_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    requires_review: bool = True
    customer_auto_publish: bool = False
    created_at_utc: str = ""


class ReviewQueueItem(BaseModel):
    review_id: str
    change_id: str
    impact_id: str
    source_id: str
    status: ReviewStatus = "pending"
    summary: str = ""
    severity: Severity = "info"
    suggested_actions: List[str] = Field(default_factory=list)
    knowledge_updates: List[Dict[str, Any]] = Field(default_factory=list)
    created_at_utc: str = ""
    reviewed_at_utc: str = ""
    reviewer_note: str = ""


class RunSummary(BaseModel):
    ok: bool = True
    run_id: str = ""
    started_utc: str = ""
    completed_utc: str = ""
    sources_checked: int = 0
    sources_failed: int = 0
    changes_detected: int = 0
    impacts_created: int = 0
    reviews_queued: int = 0
    stale_sources: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
