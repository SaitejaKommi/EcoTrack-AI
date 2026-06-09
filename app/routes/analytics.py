"""
Analytics Blueprint for CarbonWise AI.

Exposes REST API endpoints for frontend telemetry event logging and
aggregated usage statistics retrieval.

Endpoint Summary:
    POST /api/analytics/event   — Record a user interaction telemetry event.
    GET  /api/analytics/summary — Retrieve aggregated scorecard statistics.

Tracked Event Types (validated in ``validate_analytics_event``):
    - ``calculator_submitted``: Footprint calculation logged.
    - ``goal_completed``: Coaching goal marked done.
    - ``simulation_run``: Lifestyle scenario simulation executed.
    - ``ai_recommendation_accepted``: Gemini suggestion accepted by user.

Architecture role: Presentation / controller layer — thin handlers that
delegate entirely to ``AnalyticsService``. Contains no business logic.
"""

from typing import Tuple

from flask import Blueprint, Response, request, session

from app.models.schemas import validate_analytics_event
from app.routes.auth import csrf_protect, login_required
from app.services.analytics_service import AnalyticsService
from app.utils.response import error_response, success_response

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/event", methods=["POST"])
@login_required
@csrf_protect
def track_event() -> Tuple[Response, int]:
    """Persist a frontend telemetry interaction event in the analytics collection.

    Validates the event type against the allowed whitelist to prevent
    arbitrary event names from polluting the telemetry store. The metadata
    object is stored as-is alongside the event type and a UTC timestamp.

    Returns:
        Tuple[Response, int]: 200 with a success message on insertion,
        400 with a validation error when the event type is unknown or the
        payload is malformed.
    """
    user_id = session["user_id"]
    data = request.get_json(silent=True)

    is_valid, err, cleaned = validate_analytics_event(data)
    if not is_valid:
        return error_response(err, 400)

    AnalyticsService.log_event(
        user_id=user_id,
        event_type=cleaned["event_type"],
        metadata=cleaned["metadata"],
    )

    return success_response("Telemetry event logged successfully.", status_code=200)


@analytics_bp.route("/summary", methods=["GET"])
@login_required
def get_summary() -> Tuple[Response, int]:
    """Retrieve aggregated interaction counts and carbon savings for the dashboard.

    Delegates to ``AnalyticsService.get_user_analytics_summary()`` which
    counts events by type and sums the ``carbon_saved_kg`` values from
    goal-completion events.

    Returns:
        Tuple[Response, int]: 200 with the summary scorecard dict containing
        ``calculations_run``, ``goals_completed``, ``simulations_run``,
        ``recommendations_accepted``, and ``estimated_carbon_saved_kg``.
    """
    user_id = session["user_id"]
    summary = AnalyticsService.get_user_analytics_summary(user_id)
    return success_response("Telemetry summary retrieved successfully.", summary, 200)
