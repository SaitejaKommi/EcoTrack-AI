"""
Analytics Blueprint Routing for CarbonWise AI.
Tracks application user engagements and processes summary telemetry metrics.
"""

from flask import Blueprint, request, jsonify, session, Response
from typing import Tuple
from app.routes.auth import login_required, csrf_protect
from app.models.schemas import validate_analytics_event
from app.services.analytics_service import AnalyticsService

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/event', methods=['POST'])
@login_required
@csrf_protect
def track_event() -> Tuple[Response, int]:
    """Logs a frontend telemetry interaction event (e.g. simulation run, accepting suggestion)."""
    user_id = session['user_id']
    data = request.get_json(silent=True)
    
    is_valid, err, cleaned = validate_analytics_event(data)
    if not is_valid:
        return jsonify({
            "status": "error",
            "code": 400,
            "message": err
        }), 400
        
    AnalyticsService.log_event(
        user_id=user_id,
        event_type=cleaned["event_type"],
        metadata=cleaned["metadata"]
    )
    
    return jsonify({
        "status": "success",
        "code": 200,
        "message": "Telemetry event logged successfully."
    }), 200

@analytics_bp.route('/summary', methods=['GET'])
@login_required
def get_summary() -> Tuple[Response, int]:
    """Retrieves aggregated user actions scorecard (calculations count, goals, savings)."""
    user_id = session['user_id']
    summary = AnalyticsService.get_user_analytics_summary(user_id)
    
    return jsonify({
        "status": "success",
        "code": 200,
        "data": summary
    }), 200
