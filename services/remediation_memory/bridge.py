"""Remediation Memory bridge to Central Memory.

Ensures all remediation outcomes and lessons are linked to the organism's
central memory timeline for entity-level tracking and future cross-project analysis.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def link_outcome_to_memory(outcome) -> None:
    """Link remediation outcome to central memory timeline.

    Best-effort bridge — never fails the outcome write.
    """
    try:
        from services.memory.central_memory import find_entity_id
        from services.memory.organism_integration import safe_write_after_remediation_outcome

        # Find entity for this project
        entity_id = find_entity_id(project_id=outcome.project_id)
        if not entity_id:
            logger.debug(
                f"No entity found for project {outcome.project_id}, "
                f"remediation outcome {outcome.outcome_id} not linked to timeline"
            )
            return

        # Bridge to central memory
        safe_write_after_remediation_outcome(
            entity_id=entity_id,
            outcome_id=outcome.outcome_id,
            project_id=outcome.project_id,
            requirement_id=outcome.requirement_id,
            gap_id=outcome.gap_id,
            action=outcome.action_taken,
            method=outcome.implementation_method,
            category=outcome.category,
            resolution_status=outcome.resolution_status,
            duration_days=outcome.duration_days,
            cost_usd=outcome.cost_usd,
            complexity=outcome.complexity,
            success=outcome.resolution_status in ("resolved", "partial"),
            metadata={
                "blocking_factors": outcome.blocking_factors,
                "would_recommend": outcome.would_recommend,
                "lessons_learned_count": len(outcome.lessons_learned),
            },
        )

        logger.info(
            f"Linked remediation outcome {outcome.outcome_id} to entity {entity_id} timeline"
        )

    except Exception as e:
        logger.warning(
            f"Failed to link remediation outcome {outcome.outcome_id} to central memory: {e}"
        )


def link_lesson_to_memory(lesson) -> None:
    """Link remediation lesson to central memory timeline.

    Best-effort bridge — never fails the lesson write.
    """
    try:
        from services.memory.timeline import append_timeline

        # Link to each project where this lesson was observed
        for project_id in lesson.project_ids:
            try:
                from services.memory.central_memory import find_entity_id

                entity_id = find_entity_id(project_id=project_id)
                if not entity_id:
                    continue

                append_timeline(
                    entity_id,
                    event_type="remediation_lesson_learned",
                    ref_type="lesson",
                    ref_id=lesson.lesson_id,
                    payload={
                        "title": lesson.title,
                        "category": lesson.category,
                        "severity": lesson.severity,
                        "requirement_ids": lesson.requirement_ids,
                    },
                )

                logger.info(
                    f"Linked remediation lesson {lesson.lesson_id} to entity {entity_id} timeline"
                )

            except Exception as e:
                logger.warning(
                    f"Failed to link lesson {lesson.lesson_id} to project {project_id}: {e}"
                )

    except Exception as e:
        logger.warning(
            f"Failed to link remediation lesson {lesson.lesson_id} to central memory: {e}"
        )
