"""
Analytics Service for CarbonWise AI.

Records user interaction telemetry events and computes aggregated usage
statistics for the dashboard scorecard. All events are stored in the
``analytics`` database collection with a UTC timestamp.

Tracked event types (defined in ``validate_analytics_event``):
- ``calculator_submitted``: A footprint calculation was logged.
- ``goal_completed``: A coaching goal was marked done, with carbon savings.
- ``simulation_run``: A lifestyle scenario simulation was executed.
- ``ai_recommendation_accepted``: A Gemini AI suggestion was accepted by the user.

Architecture role: Business logic / service layer — consumes the database
through ``get_db()`` and exposes a clean API to route handlers without
any HTTP-layer dependencies.

Typical usage:
    from app.services.analytics_service import AnalyticsService
    AnalyticsService.log_event(user_id, "calculator_submitted", {"score": 72})
    summary = AnalyticsService.get_user_analytics_summary(user_id)
"""

import logging
from datetime import datetime
from typing import Any, Dict

from app.db import get_db

logger = logging.getLogger(__name__)

# Analytics collection event type constants
_EVENT_CALCULATOR = "calculator_submitted"
_EVENT_GOAL = "goal_completed"
_EVENT_SIMULATION = "simulation_run"
_EVENT_AI_ACCEPTED = "ai_recommendation_accepted"

# Metadata key used by goal_completed events to report carbon savings
_CARBON_SAVED_KEY = "carbon_saved_kg"


class AnalyticsService:
    """Service class for telemetry event logging and usage summary aggregation.

    All methods are ``@staticmethod`` — no instance state is held.
    """

    @staticmethod
    def log_event(
        user_id: str,
        event_type: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """Persist a user interaction event with a UTC timestamp.

        Args:
            user_id: Authenticated user identifier associated with the event.
            event_type: Categorised event name (must be one of the allowed
                types validated by ``validate_analytics_event``).
            metadata: Arbitrary key-value payload attached to the event for
                downstream analysis (e.g. ``{"score": 72}`` for a calculation).

        Returns:
            bool: Always ``True`` after successful insertion. Database write
            errors are propagated as-is to the caller.

        Raises:
            No exceptions are caught — underlying database errors propagate.
        """
        db = get_db()
        event: Dict[str, Any] = {
            "user_id": user_id,
            "event_type": event_type,
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat(),
        }
        db["analytics"].insert_one(event)
        logger.debug("[Analytics] Logged event '%s' for user '%s'.", event_type, user_id)
        return True

    @staticmethod
    def get_user_analytics_summary(user_id: str) -> Dict[str, Any]:
        """Aggregate interaction counts and carbon savings for the dashboard scorecard.

        Counts events by type using ``count_documents`` and sums the
        ``carbon_saved_kg`` metadata field from all ``goal_completed`` events
        to produce an estimated total savings figure.

        Args:
            user_id: Authenticated user identifier whose events to aggregate.

        Returns:
            Dict[str, Any]: Summary scorecard containing:
                - ``"calculations_run"``: int, total calculator submissions.
                - ``"goals_completed"``: int, total goals marked done.
                - ``"simulations_run"``: int, total simulations executed.
                - ``"recommendations_accepted"``: int, total AI suggestions accepted.
                - ``"estimated_carbon_saved_kg"``: float, sum of carbon savings
                  reported in goal-completion events.

        Raises:
            No exceptions — missing or malformed metadata values default to 0.
        """
        db = get_db()

        calc_count = db["analytics"].count_documents({"user_id": user_id, "event_type": _EVENT_CALCULATOR})
        goals_count = db["analytics"].count_documents({"user_id": user_id, "event_type": _EVENT_GOAL})
        sims_count = db["analytics"].count_documents({"user_id": user_id, "event_type": _EVENT_SIMULATION})
        accepted_recs = db["analytics"].count_documents({"user_id": user_id, "event_type": _EVENT_AI_ACCEPTED})

        total_carbon_saved = _sum_carbon_savings(db, user_id)

        return {
            "calculations_run": calc_count,
            "goals_completed": goals_count,
            "simulations_run": sims_count,
            "recommendations_accepted": accepted_recs,
            "estimated_carbon_saved_kg": round(total_carbon_saved, 2),
        }


def _sum_carbon_savings(db: Any, user_id: str) -> float:
    """Sum the ``carbon_saved_kg`` metadata field across all goal completion events.

    Iterates over every ``goal_completed`` event for the user and accumulates
    the carbon savings value from the event metadata. Non-numeric or missing
    values default to ``0.0`` to prevent aggregation failures.

    Args:
        db: Active database handle from ``get_db()``.
        user_id: Authenticated user identifier.

    Returns:
        float: Total estimated carbon saved in kg CO2e across all logged goals.
    """
    total = 0.0
    goal_events = db["analytics"].find({"user_id": user_id, "event_type": _EVENT_GOAL})
    for event in goal_events:
        meta = event.get("metadata", {})
        total += float(meta.get(_CARBON_SAVED_KEY, 0.0))
    return total
