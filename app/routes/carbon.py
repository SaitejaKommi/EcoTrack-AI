"""
Carbon Footprint Blueprint Routing for CarbonWise AI.
Exposes endpoints for calculating footprints, checking logs, simulations, and future predictions.
"""

from flask import Blueprint, request, session, Response
from typing import Tuple, Any
from app.routes.auth import login_required, csrf_protect
from app.utils.response import success_response, error_response
from app.models.schemas import validate_carbon_input, validate_simulation
from app.services.carbon_service import CarbonService
from app.services.gemini_service import GeminiService
from app.services.analytics_service import AnalyticsService

carbon_bp = Blueprint('carbon', __name__)

@carbon_bp.route('/calculate', methods=['POST'])
@login_required
@csrf_protect
def calculate() -> Tuple[Response, int]:
    """Calculates user carbon footprint, logs scores, and awards eligible badges."""
    user_id = session['user_id']
    data = request.get_json(silent=True)
    
    is_valid, err, cleaned = validate_carbon_input(data)
    if not is_valid:
        return error_response(err, 400)
        
    # Process emissions, update streak and award badge checks
    result = CarbonService.save_calculation(user_id, cleaned)
    
    # Telemetry logging
    AnalyticsService.log_event(
        user_id=user_id,
        event_type="calculator_submitted",
        metadata={"total_emissions_kg": result["emissions"]["total"], "score": result["eco_score"]}
    )
    
    return success_response("Calculation recorded successfully.", result, 200)

@carbon_bp.route('/history', methods=['GET'])
@login_required
def get_history() -> Tuple[Response, int]:
    """Retrieves list of previous calculator submissions for charting trends."""
    user_id = session['user_id']
    history = CarbonService.get_user_history(user_id)
    
    return success_response("History retrieved successfully.", history, 200)

@carbon_bp.route('/simulate', methods=['POST'])
@login_required
@csrf_protect
def simulate() -> Tuple[Response, int]:
    """Calculates potential footprint reduction under custom habits scenarios."""
    user_id = session['user_id']
    data = request.get_json(silent=True)
    
    is_valid, err, cleaned = validate_simulation(data)
    if not is_valid:
        return error_response(err, 400)
        
    result = CarbonService.simulate_reduction(cleaned)
    
    # Telemetry logging
    AnalyticsService.log_event(
        user_id=user_id,
        event_type="simulation_run",
        metadata={
            "potential_saving_kg": result["potential_reduction_kg"],
            "transit_shift": cleaned["public_transit_shift"],
            "meat_reduction": cleaned["meat_reduction"],
            "clean_energy_shift": cleaned["clean_energy_shift"]
        }
    )
    
    return success_response("Simulation recorded successfully.", result, 200)

@carbon_bp.route('/predict', methods=['GET'])
@login_required
def predict() -> Tuple[Response, int]:
    """Forecasts emissions in 30 and 90 days using user history and AI reasoning."""
    user_id = session['user_id']
    history = CarbonService.get_user_history(user_id, limit=5)
    
    if not history:
        return error_response("No calculator entries found. Please log a calculation first to forecast trends.", 400)
        
    result = GeminiService.predict_future_footprint(history)
    return success_response("Predictions generated successfully.", result, 200)
