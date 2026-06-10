"""Remediation Memory — Track what was done, what worked, what failed.

First-class organism organ for capturing remediation outcomes, implementation
methods, costs, timelines, and lessons learned. Ensures no remediation
knowledge is ever lost.

Connected to:
- Central Memory (entity timeline)
- Compliance Health (requirement tracking)
- Cognition (gap resolution strategies)
- Evidence Intelligence (gap detection)

Future aggregation layer will mine cross-company patterns from this foundation.
"""
from .schemas import (
    RemediationOutcome,
    RemediationLesson,
    ImplementationMethod,
    ResolutionStatus,
    ComplexityLevel,
    OutcomeSummary,
)
from .storage import (
    record_outcome,
    record_lesson,
    record_implementation_method,
    load_outcomes,
    load_lessons,
    load_methods,
    get_outcome,
    get_project_outcomes,
    get_requirement_outcomes,
)
from .bridge import (
    link_outcome_to_memory,
    link_lesson_to_memory,
)

__all__ = [
    # Schemas
    "RemediationOutcome",
    "RemediationLesson",
    "ImplementationMethod",
    "ResolutionStatus",
    "ComplexityLevel",
    "OutcomeSummary",
    # Storage
    "record_outcome",
    "record_lesson",
    "record_implementation_method",
    "load_outcomes",
    "load_lessons",
    "load_methods",
    "get_outcome",
    "get_project_outcomes",
    "get_requirement_outcomes",
    # Bridge
    "link_outcome_to_memory",
    "link_lesson_to_memory",
]
