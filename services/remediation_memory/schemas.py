"""Remediation Memory schemas — permanent record of what was done and what was learned."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResolutionStatus(str, Enum):
    """Resolution status for remediation attempts."""

    RESOLVED = "resolved"  # Gap fully closed, requirement verified
    PARTIAL = "partial"  # Some progress made, not complete
    BLOCKED = "blocked"  # Cannot proceed due to external blocker
    FAILED = "failed"  # Attempted but unsuccessful
    IN_PROGRESS = "in_progress"  # Currently being worked


class ComplexityLevel(str, Enum):
    """Complexity rating for remediation actions."""

    TRIVIAL = "trivial"  # <1 day, no cost
    LOW = "low"  # 1-3 days, minimal cost
    MEDIUM = "medium"  # 1-2 weeks, moderate cost
    HIGH = "high"  # 2-4 weeks, significant cost
    CRITICAL = "critical"  # >4 weeks, major cost/effort


class RemediationOutcome(BaseModel):
    """Permanent record of a remediation attempt and its outcome.

    This is the foundational data structure for organism learning.
    Every remediation action must be captured here to prevent knowledge loss.
    """

    outcome_id: str = Field(..., description="Unique outcome identifier (REM-xxx)")
    project_id: str = Field(..., description="Project this remediation belongs to")
    requirement_id: Optional[str] = Field(
        None, description="Compliance requirement being addressed (e.g., cmmc.ac.1.001)"
    )
    gap_id: Optional[str] = Field(
        None, description="Evidence gap being closed (e.g., GAP-xxx)"
    )

    # What was attempted
    action_taken: str = Field(
        ..., description="Description of the remediation action attempted"
    )
    implementation_method: str = Field(
        ..., description="Method/approach used (e.g., 'implement_mfa_azure_ad')"
    )
    category: str = Field(
        default="general",
        description="Custom category (e.g., 'access_control', 'incident_response', 'documentation')",
    )

    # Outcome
    resolution_status: ResolutionStatus = Field(
        ..., description="Final resolution status"
    )
    success_evidence: Optional[str] = Field(
        None, description="Evidence that remediation succeeded (artifact refs, verification notes)"
    )
    blocking_factors: List[str] = Field(
        default_factory=list,
        description="Factors that blocked or slowed progress (e.g., 'budget', 'vendor_delay', 'policy_approval')",
    )

    # Cost and timeline
    duration_days: Optional[int] = Field(
        None, description="Actual duration in days from start to completion"
    )
    cost_usd: Optional[float] = Field(
        None, description="Actual cost in USD (if tracked)"
    )
    estimated_duration_days: Optional[int] = Field(
        None, description="Original estimate for comparison"
    )
    estimated_cost_usd: Optional[float] = Field(
        None, description="Original cost estimate"
    )
    complexity: Optional[ComplexityLevel] = Field(
        None, description="Complexity rating"
    )

    # Learning
    lessons_learned: List[str] = Field(
        default_factory=list,
        description="Key lessons from this remediation (separate from formal RemediationLesson records)",
    )
    would_recommend: Optional[bool] = Field(
        None, description="Would operator recommend this approach again?"
    )
    alternative_approaches: List[str] = Field(
        default_factory=list,
        description="Alternative approaches that were considered or could be tried next",
    )

    # Metadata
    operator_email: Optional[str] = Field(
        None, description="Operator who recorded this outcome"
    )
    when_utc: str = Field(..., description="When this outcome was recorded (ISO 8601)")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional custom metadata"
    )

    class Config:
        use_enum_values = True


class RemediationLesson(BaseModel):
    """Formal lesson learned from remediation experience.

    Lessons can be linked to multiple outcomes and represent generalizable
    knowledge that should inform future remediation decisions.
    """

    lesson_id: str = Field(..., description="Unique lesson identifier (LESSON-xxx)")
    title: str = Field(..., description="Short lesson title")
    description: str = Field(..., description="Detailed lesson description")
    category: str = Field(
        default="general", description="Lesson category for future retrieval"
    )

    # Context
    requirement_ids: List[str] = Field(
        default_factory=list,
        description="Requirements this lesson applies to",
    )
    outcome_ids: List[str] = Field(
        default_factory=list,
        description="Remediation outcomes this lesson was learned from",
    )
    project_ids: List[str] = Field(
        default_factory=list,
        description="Projects where this lesson was observed",
    )

    # Learning
    what_worked: Optional[str] = Field(None, description="What worked well")
    what_failed: Optional[str] = Field(None, description="What didn't work")
    recommended_approach: Optional[str] = Field(
        None, description="Recommended approach based on experience"
    )
    avoid_approach: Optional[str] = Field(
        None, description="Approach to avoid based on experience"
    )

    # Metadata
    severity: str = Field(
        default="info",
        description="Lesson severity (critical, high, medium, low, info)",
    )
    operator_email: Optional[str] = Field(
        None, description="Operator who recorded this lesson"
    )
    when_utc: str = Field(..., description="When this lesson was recorded (ISO 8601)")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional custom metadata"
    )


class ImplementationMethod(BaseModel):
    """Reusable implementation method for a specific type of remediation.

    Methods are implementation templates that can be referenced by future
    remediation attempts. They represent accumulated organizational knowledge.
    """

    method_id: str = Field(..., description="Unique method identifier (METHOD-xxx)")
    name: str = Field(..., description="Method name (e.g., 'implement_mfa_azure_ad')")
    description: str = Field(..., description="Detailed method description")
    category: str = Field(
        default="general", description="Method category (e.g., 'access_control')"
    )

    # Applicability
    requirement_ids: List[str] = Field(
        default_factory=list,
        description="Requirements this method can address",
    )
    gap_types: List[str] = Field(
        default_factory=list,
        description="Gap types this method can close",
    )

    # Implementation details
    steps: List[str] = Field(
        default_factory=list, description="Step-by-step implementation guide"
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Prerequisites before starting this method",
    )
    tools_required: List[str] = Field(
        default_factory=list,
        description="Tools or systems required (e.g., 'Azure AD', 'AWS IAM')",
    )

    # Estimates
    typical_duration_days: Optional[int] = Field(
        None, description="Typical duration in days"
    )
    typical_cost_usd: Optional[float] = Field(
        None, description="Typical cost in USD"
    )
    complexity: Optional[ComplexityLevel] = Field(
        None, description="Typical complexity level"
    )

    # Success tracking
    times_used: int = Field(
        default=0, description="Number of times this method has been used"
    )
    times_succeeded: int = Field(
        default=0, description="Number of times this method succeeded"
    )
    success_rate: Optional[float] = Field(
        None, description="Calculated success rate (times_succeeded / times_used)"
    )

    # Metadata
    created_by: Optional[str] = Field(
        None, description="Operator who created this method"
    )
    created_utc: str = Field(
        ..., description="When this method was created (ISO 8601)"
    )
    updated_utc: Optional[str] = Field(
        None, description="When this method was last updated"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional custom metadata"
    )

    class Config:
        use_enum_values = True


class OutcomeSummary(BaseModel):
    """Summary statistics for remediation outcomes.

    Used by operator dashboard and future learning layer.
    """

    total_outcomes: int = Field(default=0)
    resolved_count: int = Field(default=0)
    partial_count: int = Field(default=0)
    blocked_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    in_progress_count: int = Field(default=0)

    total_cost_usd: float = Field(default=0.0)
    total_duration_days: int = Field(default=0)
    avg_cost_usd: Optional[float] = Field(None)
    avg_duration_days: Optional[float] = Field(None)

    success_rate: Optional[float] = Field(
        None, description="(resolved + partial) / total"
    )

    by_category: Dict[str, int] = Field(
        default_factory=dict, description="Outcome counts by category"
    )
    by_complexity: Dict[str, int] = Field(
        default_factory=dict, description="Outcome counts by complexity"
    )
    top_blocking_factors: List[tuple] = Field(
        default_factory=list, description="Most common blocking factors [(factor, count), ...]"
    )
