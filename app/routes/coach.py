"""
AI Coach Blueprint for CarbonWise AI.

Exposes REST API endpoints for the AI coaching and gamification features:
personalised sustainability insights, smart action plans, and goal completion
tracking.

Endpoint Summary:
    GET  /api/coach/insights        — Fetch personalised coaching insights.
    GET  /api/coach/plan            — Retrieve a structured daily/weekly/monthly plan.
    POST /api/coach/goals/complete  — Mark a coaching goal as completed.

Coaching Pipeline:
    1. Fetch the user's most recent footprint document from the database.
    2. Attach the session username for prompt personalisation.
    3. Delegate to ``GeminiService`` which serves from the TTL cache or calls the API.
    4. Return the structured JSON response envelope.

Architecture role: Presentation / controller layer — thin handler functions
that delegate all business logic to ``CarbonService``, ``GeminiService``,
and ``AnalyticsService``.
"""

from typing import Tuple

from flask import Blueprint, Response, request, session

from app.routes.auth import csrf_protect, login_required
from app.services.analytics_service import AnalyticsService
from app.services.carbon_service import CarbonService
from app.services.gemini_service import GeminiService
from app.utils.response import error_response, success_response

coach_bp = Blueprint("coach", __name__)

# Default username displayed when the session key is absent
_DEFAULT_USERNAME: str = "Eco-Warrior"

# Number of history entries fetched for insight/plan generation (only need latest)
_INSIGHT_HISTORY_LIMIT: int = 1


@coach_bp.route("/insights", methods=["GET"])
@login_required
def get_insights() -> Tuple[Response, int]:
    """Generate personalised coaching recommendations from the user's latest footprint.

    Fetches the single most recent calculation document and passes it to
    ``GeminiService.generate_coaching_insights()``. Returns 400 when no
    calculation history exists, directing the user to complete the calculator first.

    The username is injected from the session into the footprint document before
    the API call so that the Gemini prompt can address the user by name.

    Returns:
        Tuple[Response, int]: 200 with insights, suggestions, and weekly goals
        on success, 400 when no history is available.
    """
    user_id = session["user_id"]
    history = CarbonService.get_user_history(user_id, limit=_INSIGHT_HISTORY_LIMIT)

    if not history:
        return error_response(
            "Please log a carbon calculation first to unlock personalized AI insights.",
            400,
        )

    latest_footprint = history[0]
    # Attach username for Gemini prompt personalisation without a separate DB query
    latest_footprint["username"] = session.get("username", _DEFAULT_USERNAME)

    insights = GeminiService.generate_coaching_insights(user_id, latest_footprint)
    return success_response("Coach insights retrieved successfully.", insights, 200)


@coach_bp.route("/plan", methods=["GET"])
@login_required
def get_action_plan() -> Tuple[Response, int]:
    """Retrieve a structured daily, weekly, and monthly sustainable habit action plan.

    Delegates to ``GeminiService.generate_action_plan()`` using the user's
    latest footprint context. Returns 400 when no history is available.

    Returns:
        Tuple[Response, int]: 200 with the multi-schedule action plan on success,
        400 when no history is available.
    """
    user_id = session["user_id"]
    history = CarbonService.get_user_history(user_id, limit=_INSIGHT_HISTORY_LIMIT)

    if not history:
        return error_response(
            "Please log a carbon calculation first to construct an actionable reduction roadmap.",
            400,
        )

    latest_footprint = history[0]
    plan = GeminiService.generate_action_plan(user_id, latest_footprint)
    return success_response("Action plan retrieved successfully.", plan, 200)


@coach_bp.route("/goals/complete", methods=["POST"])
@login_required
@csrf_protect
def complete_goal() -> Tuple[Response, int]:
    """Record a coaching goal completion and return the updated analytics summary.

    Logs a ``goal_completed`` telemetry event with the goal title and
    estimated carbon savings. Returns the full analytics summary so the
    frontend can immediately refresh the scorecard statistics.

    Returns:
        Tuple[Response, int]: 200 with the updated analytics summary on success,
        400 when the goal title is missing or empty.
    """
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}

    goal_title = data.get("goal_title", "").strip()
    if not goal_title:
        return error_response("Goal title is required to mark a goal completed.", 400)

    # Coerce carbon saved to a non-negative float, defaulting to 0 on invalid input
    raw_carbon_saved = data.get("carbon_saved_kg", 0.0)
    try:
        carbon_saved = max(0.0, float(raw_carbon_saved))
    except (ValueError, TypeError):
        carbon_saved = 0.0

    AnalyticsService.log_event(
        user_id=user_id,
        event_type="goal_completed",
        metadata={"goal_title": goal_title, "carbon_saved_kg": carbon_saved},
    )

    # Return the refreshed summary so the dashboard scorecard updates without
    # a separate network request
    summary = AnalyticsService.get_user_analytics_summary(user_id)
    return success_response(
        f"Goal '{goal_title}' marked completed. Carbon savings tracked!",
        summary,
        200,
    )
