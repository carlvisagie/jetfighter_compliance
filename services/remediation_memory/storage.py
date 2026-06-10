"""Remediation Memory storage layer — append-only permanent record."""
from __future__ import annotations

import json
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import DATA
from .schemas import (
    ComplexityLevel,
    ImplementationMethod,
    OutcomeSummary,
    RemediationLesson,
    RemediationOutcome,
    ResolutionStatus,
)

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _remediation_dir() -> Path:
    """Get remediation memory root directory."""
    d = DATA / "remediation_memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _outcomes_path() -> Path:
    return _remediation_dir() / "outcomes.jsonl"


def _lessons_path() -> Path:
    return _remediation_dir() / "lessons.jsonl"


def _methods_path() -> Path:
    return _remediation_dir() / "methods.jsonl"


def _generate_outcome_id() -> str:
    return f"REM-{uuid.uuid4().hex[:10]}"


def _generate_lesson_id() -> str:
    return f"LESSON-{uuid.uuid4().hex[:10]}"


def _generate_method_id() -> str:
    return f"METHOD-{uuid.uuid4().hex[:10]}"


# ============================================================================
# OUTCOMES
# ============================================================================


def record_outcome(
    *,
    project_id: str,
    action_taken: str,
    implementation_method: str,
    resolution_status: ResolutionStatus | str,
    requirement_id: Optional[str] = None,
    gap_id: Optional[str] = None,
    category: str = "general",
    success_evidence: Optional[str] = None,
    blocking_factors: Optional[List[str]] = None,
    duration_days: Optional[int] = None,
    cost_usd: Optional[float] = None,
    estimated_duration_days: Optional[int] = None,
    estimated_cost_usd: Optional[float] = None,
    complexity: Optional[ComplexityLevel | str] = None,
    lessons_learned: Optional[List[str]] = None,
    would_recommend: Optional[bool] = None,
    alternative_approaches: Optional[List[str]] = None,
    operator_email: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> RemediationOutcome:
    """Record a remediation outcome.

    This is the primary entry point for capturing remediation knowledge.
    Every remediation action should be recorded here to prevent knowledge loss.

    Automatically:
    - Generates outcome_id
    - Timestamps the record
    - Appends to outcomes.jsonl
    - Links to central memory (via bridge)

    Returns the created RemediationOutcome for further processing.
    """
    outcome_id = _generate_outcome_id()

    outcome = RemediationOutcome(
        outcome_id=outcome_id,
        project_id=project_id,
        requirement_id=requirement_id,
        gap_id=gap_id,
        action_taken=action_taken,
        implementation_method=implementation_method,
        category=category,
        resolution_status=resolution_status
        if isinstance(resolution_status, ResolutionStatus)
        else ResolutionStatus(resolution_status),
        success_evidence=success_evidence,
        blocking_factors=blocking_factors or [],
        duration_days=duration_days,
        cost_usd=cost_usd,
        estimated_duration_days=estimated_duration_days,
        estimated_cost_usd=estimated_cost_usd,
        complexity=complexity
        if isinstance(complexity, (ComplexityLevel, type(None)))
        else ComplexityLevel(complexity),
        lessons_learned=lessons_learned or [],
        would_recommend=would_recommend,
        alternative_approaches=alternative_approaches or [],
        operator_email=operator_email,
        when_utc=_utc_now(),
        metadata=metadata or {},
    )

    # Append to outcomes.jsonl (append-only, never delete)
    path = _outcomes_path()
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(outcome.model_dump_json() + "\n")
        logger.info(
            f"Recorded remediation outcome {outcome_id} for project {project_id}: "
            f"{resolution_status}, method={implementation_method}"
        )
    except Exception as e:
        logger.error(f"Failed to record remediation outcome {outcome_id}: {e}")
        raise

    # Link to central memory (best-effort, never fails the write)
    try:
        from .bridge import link_outcome_to_memory

        link_outcome_to_memory(outcome)
    except Exception as e:
        logger.warning(
            f"Failed to link remediation outcome {outcome_id} to central memory: {e}"
        )

    return outcome


def load_outcomes(
    *,
    limit: Optional[int] = None,
    project_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    category: Optional[str] = None,
    resolution_status: Optional[ResolutionStatus | str] = None,
) -> List[RemediationOutcome]:
    """Load remediation outcomes with optional filters.

    Returns most recent outcomes first.
    """
    path = _outcomes_path()
    if not path.exists():
        return []

    outcomes: List[RemediationOutcome] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    outcome = RemediationOutcome(**data)

                    # Apply filters
                    if project_id and outcome.project_id != project_id:
                        continue
                    if requirement_id and outcome.requirement_id != requirement_id:
                        continue
                    if category and outcome.category != category:
                        continue
                    if resolution_status and outcome.resolution_status != resolution_status:
                        continue

                    outcomes.append(outcome)
                except Exception as e:
                    logger.warning(f"Skipping malformed outcome record: {e}")
                    continue
    except Exception as e:
        logger.error(f"Failed to load remediation outcomes: {e}")
        return []

    # Most recent first
    outcomes.reverse()

    if limit:
        outcomes = outcomes[:limit]

    return outcomes


def get_outcome(outcome_id: str) -> Optional[RemediationOutcome]:
    """Get a specific remediation outcome by ID."""
    outcomes = load_outcomes()
    for outcome in outcomes:
        if outcome.outcome_id == outcome_id:
            return outcome
    return None


def get_project_outcomes(project_id: str) -> List[RemediationOutcome]:
    """Get all remediation outcomes for a specific project."""
    return load_outcomes(project_id=project_id)


def get_requirement_outcomes(requirement_id: str) -> List[RemediationOutcome]:
    """Get all remediation outcomes for a specific requirement.

    Future learning layer will use this to compute requirement difficulty scores.
    """
    return load_outcomes(requirement_id=requirement_id)


def get_outcome_summary(
    *,
    project_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    category: Optional[str] = None,
) -> OutcomeSummary:
    """Compute summary statistics for remediation outcomes.

    Used by operator dashboard and future learning layer.
    """
    outcomes = load_outcomes(
        project_id=project_id, requirement_id=requirement_id, category=category
    )

    if not outcomes:
        return OutcomeSummary()

    resolved = sum(1 for o in outcomes if o.resolution_status == ResolutionStatus.RESOLVED)
    partial = sum(1 for o in outcomes if o.resolution_status == ResolutionStatus.PARTIAL)
    blocked = sum(1 for o in outcomes if o.resolution_status == ResolutionStatus.BLOCKED)
    failed = sum(1 for o in outcomes if o.resolution_status == ResolutionStatus.FAILED)
    in_progress = sum(
        1 for o in outcomes if o.resolution_status == ResolutionStatus.IN_PROGRESS
    )

    total_cost = sum(o.cost_usd for o in outcomes if o.cost_usd is not None)
    total_duration = sum(o.duration_days for o in outcomes if o.duration_days is not None)
    cost_count = sum(1 for o in outcomes if o.cost_usd is not None)
    duration_count = sum(1 for o in outcomes if o.duration_days is not None)

    by_category: Dict[str, int] = {}
    for o in outcomes:
        by_category[o.category] = by_category.get(o.category, 0) + 1

    by_complexity: Dict[str, int] = {}
    for o in outcomes:
        if o.complexity:
            by_complexity[o.complexity] = by_complexity.get(o.complexity, 0) + 1

    # Aggregate blocking factors
    all_blocking_factors: List[str] = []
    for o in outcomes:
        all_blocking_factors.extend(o.blocking_factors)
    top_blocking = Counter(all_blocking_factors).most_common(10)

    return OutcomeSummary(
        total_outcomes=len(outcomes),
        resolved_count=resolved,
        partial_count=partial,
        blocked_count=blocked,
        failed_count=failed,
        in_progress_count=in_progress,
        total_cost_usd=total_cost,
        total_duration_days=total_duration,
        avg_cost_usd=total_cost / cost_count if cost_count > 0 else None,
        avg_duration_days=total_duration / duration_count if duration_count > 0 else None,
        success_rate=(resolved + partial) / len(outcomes) if outcomes else None,
        by_category=by_category,
        by_complexity=by_complexity,
        top_blocking_factors=top_blocking,
    )


# ============================================================================
# LESSONS
# ============================================================================


def record_lesson(
    *,
    title: str,
    description: str,
    category: str = "general",
    requirement_ids: Optional[List[str]] = None,
    outcome_ids: Optional[List[str]] = None,
    project_ids: Optional[List[str]] = None,
    what_worked: Optional[str] = None,
    what_failed: Optional[str] = None,
    recommended_approach: Optional[str] = None,
    avoid_approach: Optional[str] = None,
    severity: str = "info",
    operator_email: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> RemediationLesson:
    """Record a formal lesson learned from remediation experience."""
    lesson_id = _generate_lesson_id()

    lesson = RemediationLesson(
        lesson_id=lesson_id,
        title=title,
        description=description,
        category=category,
        requirement_ids=requirement_ids or [],
        outcome_ids=outcome_ids or [],
        project_ids=project_ids or [],
        what_worked=what_worked,
        what_failed=what_failed,
        recommended_approach=recommended_approach,
        avoid_approach=avoid_approach,
        severity=severity,
        operator_email=operator_email,
        when_utc=_utc_now(),
        metadata=metadata or {},
    )

    path = _lessons_path()
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(lesson.model_dump_json() + "\n")
        logger.info(f"Recorded remediation lesson {lesson_id}: {title}")
    except Exception as e:
        logger.error(f"Failed to record remediation lesson {lesson_id}: {e}")
        raise

    # Link to central memory
    try:
        from .bridge import link_lesson_to_memory

        link_lesson_to_memory(lesson)
    except Exception as e:
        logger.warning(
            f"Failed to link remediation lesson {lesson_id} to central memory: {e}"
        )

    return lesson


def load_lessons(
    *,
    limit: Optional[int] = None,
    category: Optional[str] = None,
    requirement_id: Optional[str] = None,
) -> List[RemediationLesson]:
    """Load remediation lessons with optional filters."""
    path = _lessons_path()
    if not path.exists():
        return []

    lessons: List[RemediationLesson] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    lesson = RemediationLesson(**data)

                    if category and lesson.category != category:
                        continue
                    if requirement_id and requirement_id not in lesson.requirement_ids:
                        continue

                    lessons.append(lesson)
                except Exception as e:
                    logger.warning(f"Skipping malformed lesson record: {e}")
                    continue
    except Exception as e:
        logger.error(f"Failed to load remediation lessons: {e}")
        return []

    lessons.reverse()

    if limit:
        lessons = lessons[:limit]

    return lessons


# ============================================================================
# IMPLEMENTATION METHODS
# ============================================================================


def record_implementation_method(
    *,
    name: str,
    description: str,
    category: str = "general",
    requirement_ids: Optional[List[str]] = None,
    gap_types: Optional[List[str]] = None,
    steps: Optional[List[str]] = None,
    prerequisites: Optional[List[str]] = None,
    tools_required: Optional[List[str]] = None,
    typical_duration_days: Optional[int] = None,
    typical_cost_usd: Optional[float] = None,
    complexity: Optional[ComplexityLevel | str] = None,
    created_by: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ImplementationMethod:
    """Record a reusable implementation method."""
    method_id = _generate_method_id()

    method = ImplementationMethod(
        method_id=method_id,
        name=name,
        description=description,
        category=category,
        requirement_ids=requirement_ids or [],
        gap_types=gap_types or [],
        steps=steps or [],
        prerequisites=prerequisites or [],
        tools_required=tools_required or [],
        typical_duration_days=typical_duration_days,
        typical_cost_usd=typical_cost_usd,
        complexity=complexity
        if isinstance(complexity, (ComplexityLevel, type(None)))
        else ComplexityLevel(complexity),
        times_used=0,
        times_succeeded=0,
        success_rate=None,
        created_by=created_by,
        created_utc=_utc_now(),
        metadata=metadata or {},
    )

    path = _methods_path()
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(method.model_dump_json() + "\n")
        logger.info(f"Recorded implementation method {method_id}: {name}")
    except Exception as e:
        logger.error(f"Failed to record implementation method {method_id}: {e}")
        raise

    return method


def load_methods(
    *,
    limit: Optional[int] = None,
    category: Optional[str] = None,
    requirement_id: Optional[str] = None,
) -> List[ImplementationMethod]:
    """Load implementation methods with optional filters."""
    path = _methods_path()
    if not path.exists():
        return []

    methods: List[ImplementationMethod] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    method = ImplementationMethod(**data)

                    if category and method.category != category:
                        continue
                    if requirement_id and requirement_id not in method.requirement_ids:
                        continue

                    methods.append(method)
                except Exception as e:
                    logger.warning(f"Skipping malformed method record: {e}")
                    continue
    except Exception as e:
        logger.error(f"Failed to load implementation methods: {e}")
        return []

    methods.reverse()

    if limit:
        methods = methods[:limit]

    return methods
