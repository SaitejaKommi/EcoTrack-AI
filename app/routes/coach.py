"""
AI Coach Blueprint Routing for CarbonWise AI.
Serves personalized recommendations, AI goals, and tracks achievements.
"""

from flask import Blueprint, jsonify, session, request, Response
from typing import Tuple
from app.routes.auth import login_required, csrf_protect
from app.services.carbon_service import CarbonService
from app.services.gemini_service import GeminiService
from app.services.analytics_service import AnalyticsService

coach_bp = Blueprint('coach', __name__)

@coach_bp.route('/insights', methods=['GET'])
@login_required
def get_insights() -> Tuple[Response, int]:
    """Generates personalized coaching recommendations based on the user's latest calculation."""
    user_id = session['user_id']
    history = CarbonService.get_user_history(user_id, limit=1)
    
    if not history:
        return jsonify({
            "status": "error",
            "code": 400,
            "message": "Please log a carbon calculation first to unlock personalized AI insights."
        }), 400
        
    latest_footprint = history[0]
    # Fetch user username from session
    latest_footprint["username"] = session.get("username", "Eco-Warrior")
    
    insights = GeminiService.generate_coaching_insights(user_id, latest_footprint)
    return jsonify({
        "status": "success",
        "code": 200,
        "data": insights
    }), 200

@coach_bp.route('/plan', methods=['GET'])
@login_required
def get_action_plan() -> Tuple[Response, int]:
    """Generates a structured daily, weekly, and monthly action plan based on user emissions."""
    user_id = session['user_id']
    history = CarbonService.get_user_history(user_id, limit=1)
    
    if not history:
        return jsonify({
            "status": "error",
            "code": 400,
            "message": "Please log a carbon calculation first to construct an actionable reduction roadmap."
        }), 400
        
    latest_footprint = history[0]
    plan = GeminiService.generate_action_plan(user_id, latest_footprint)
    return jsonify({
        "status": "success",
        "code": 200,
        "data": plan
    }), 200

@coach_bp.route('/goals/complete', methods=['POST'])
@login_required
@csrf_protect
def complete_goal() -> Tuple[Response, int]:
    """Marks a coaching goal or habit card as completed, logging points and carbon savings."""
    user_id = session['user_id']
    data = request.get_json(silent=True) or {}
    
    goal_title = data.get("goal_title", "").strip()
    carbon_saved = data.get("carbon_saved_kg", 0.0)
    
    if not goal_title:
        return jsonify({
            "status": "error",
            "code": 400,
            "message": "Goal title is required to mark a goal completed."
        }), 400
        
    # Standardize carbon saved as positive float
    try:
        carbon_saved = max(0.0, float(carbon_saved))
    except (ValueError, TypeError):
        carbon_saved = 0.0
        
    # Log the completion in telemetry
    AnalyticsService.log_event(
        user_id=user_id,
        event_type="goal_completed",
        metadata={
            "goal_title": goal_title,
            "carbon_saved_kg": carbon_saved
        }
    )
    
    # Fetch updated user telemetry summary
    summary = AnalyticsService.get_user_analytics_summary(user_id)
    return jsonify({
        "status": "success",
        "code": 200,
        "message": f"Goal '{goal_title}' marked completed. Carbon savings tracked!",
        "data": summary
    }), 200
