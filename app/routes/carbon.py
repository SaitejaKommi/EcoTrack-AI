"""
Carbon Footprint Blueprint for CarbonWise AI.

Exposes REST API endpoints for the core carbon calculation pipeline:
submitting footprint data, retrieving historical entries, running lifestyle
scenario simulations, and requesting AI-powered future projections.

All endpoints require an active user session (``@login_required``). Stateful
endpoints also enforce CSRF header validation (``@csrf_protect``).

Endpoint Summary:
    POST /api/carbon/calculate  — Calculate and persist a footprint entry.
    GET  /api/carbon/history    — Retrieve historical footprint entries.
    POST /api/carbon/simulate   — Project emissions under a habit change scenario.
    GET  /api/carbon/predict    — Forecast 30-day and 90-day emission trajectories.

Architecture role: Presentation / controller layer — thin handler layer that
delegates all business logic to ``CarbonService`` and ``GeminiService``.
"""

from typing import Tuple

from flask import Blueprint, Response, request, session

from app.models.schemas import validate_carbon_input, validate_simulation
from app.routes.auth import csrf_protect, login_required
from app.services.analytics_service import AnalyticsService
from app.services.carbon_service import CarbonService
from app.services.gemini_service import GeminiService
from app.utils.response import error_response, success_response

carbon_bp = Blueprint("carbon", __name__)

# Limit used when fetching history for the predict endpoint
_PREDICT_HISTORY_LIMIT: int = 5


@carbon_bp.route("/calculate", methods=["POST"])
@login_required
@csrf_protect
def calculate() -> Tuple[Response, int]:
    """Calculate a monthly carbon footprint and persist the result.

    Validates the JSON payload through ``validate_carbon_input()``, delegates
    the full pipeline to ``CarbonService.save_calculation()`` (emissions →
    eco score → streak → badge evaluation → database insert), then logs a
    telemetry event for dashboard statistics.

    Returns:
        Tuple[Response, int]: 200 with the full calculation document on success,
        400 with a validation error message on failure.
    """
    user_id = session["user_id"]
    data = request.get_json(silent=True)

    is_valid, err, cleaned = validate_carbon_input(data)
    if not is_valid:
        return error_response(err, 400)

    # Emit, score, streak, badge pipeline — returns a complete document
    result = CarbonService.save_calculation(user_id, cleaned)

    AnalyticsService.log_event(
        user_id=user_id,
        event_type="calculator_submitted",
        metadata={
            "total_emissions_kg": result["emissions"]["total"],
            "score": result["eco_score"],
        },
    )

    return success_response("Calculation recorded successfully.", result, 200)


@carbon_bp.route("/history", methods=["GET"])
@login_required
def get_history() -> Tuple[Response, int]:
    """Return the authenticated user's previous footprint submissions.

    Retrieves up to 12 historical records ordered newest-first, which the
    frontend uses to render the historical trend line on the chart.

    Returns:
        Tuple[Response, int]: 200 with a list of calculation documents.
    """
    user_id = session["user_id"]
    history = CarbonService.get_user_history(user_id)
    return success_response("History retrieved successfully.", history, 200)


@carbon_bp.route("/simulate", methods=["POST"])
@login_required
@csrf_protect
def simulate() -> Tuple[Response, int]:
    """Project emission reductions under a hypothetical lifestyle change scenario.

    Accepts percentage shift sliders for transit adoption, diet improvement,
    and clean energy transition. Validates and cleans the payload, passes it
    to the simulation engine, then logs the simulation event for telemetry.

    Returns:
        Tuple[Response, int]: 200 with the comparative reduction analysis on
        success, 400 with a validation error on failure.
    """
    user_id = session["user_id"]
    data = request.get_json(silent=True)

    is_valid, err, cleaned = validate_simulation(data)
    if not is_valid:
        return error_response(err, 400)

    result = CarbonService.simulate_reduction(cleaned)

    AnalyticsService.log_event(
        user_id=user_id,
        event_type="simulation_run",
        metadata={
            "potential_saving_kg": result["potential_reduction_kg"],
            "transit_shift": cleaned["public_transit_shift"],
            "meat_reduction": cleaned["meat_reduction"],
            "clean_energy_shift": cleaned["clean_energy_shift"],
        },
    )

    return success_response("Simulation recorded successfully.", result, 200)


@carbon_bp.route("/predict", methods=["GET"])
@login_required
def predict() -> Tuple[Response, int]:
    """Forecast 30-day and 90-day carbon emission trajectories using AI.

    Fetches the user's most recent ``_PREDICT_HISTORY_LIMIT`` calculations and
    passes them to ``GeminiService.predict_future_footprint()``. Returns 400
    when the user has no recorded calculations, prompting them to log data first.

    Returns:
        Tuple[Response, int]: 200 with projection and reasoning on success,
        400 with a message directing the user to log a calculation first.
    """
    user_id = session["user_id"]
    history = CarbonService.get_user_history(user_id, limit=_PREDICT_HISTORY_LIMIT)

    if not history:
        return error_response(
            "No calculator entries found. Please log a calculation first to forecast trends.",
            400,
        )

    result = GeminiService.predict_future_footprint(history)
    return success_response("Predictions generated successfully.", result, 200)
