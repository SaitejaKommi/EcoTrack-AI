"""
Analytics Service Module for CarbonWise AI.
Records user interactions, logs telemetry parameters, and provides dashboard statistics.
"""

from datetime import datetime
from typing import Dict, Any, List
from app.db import get_db

class AnalyticsService:
    """Service class tracking application telemetry and usage statistics."""

    @staticmethod
    def log_event(user_id: str, event_type: str, metadata: Dict[str, Any]) -> bool:
        """
        Inserts a new telemetry event entry into the database.
        """
        db = get_db()
        event = {
            "user_id": user_id,
            "event_type": event_type,
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat()
        }
        db["analytics"].insert_one(event)
        return True

    @staticmethod
    def get_user_analytics_summary(user_id: str) -> Dict[str, Any]:
        """
        Aggregates logs to display a user-friendly tracking scorecard.
        """
        db = get_db()
        
        # Pull counts for specific event categories
        calc_count = db["analytics"].count_documents({"user_id": user_id, "event_type": "calculator_submitted"})
        goals_count = db["analytics"].count_documents({"user_id": user_id, "event_type": "goal_completed"})
        sims_count = db["analytics"].count_documents({"user_id": user_id, "event_type": "simulation_run"})
        accepted_recs = db["analytics"].count_documents({"user_id": user_id, "event_type": "ai_recommendation_accepted"})

        # Get total savings achieved (sum up differences between previous calculation totals and latest, or simple telemetry logs)
        # Let's see: user can report savings in metadata during goal completions.
        # Let's extract that from completed goals.
        total_carbon_saved = 0.0
        goal_events = db["analytics"].find({"user_id": user_id, "event_type": "goal_completed"})
        for event in goal_events:
            meta = event.get("metadata", {})
            # Read saved carbon from goal metadata if present
            total_carbon_saved += float(meta.get("carbon_saved_kg", 0.0))

        return {
            "calculations_run": calc_count,
            "goals_completed": goals_count,
            "simulations_run": sims_count,
            "recommendations_accepted": accepted_recs,
            "estimated_carbon_saved_kg": round(total_carbon_saved, 2)
        }
