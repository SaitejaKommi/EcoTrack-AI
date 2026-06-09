"""
Routes Package for CarbonWise AI.

This package contains the Flask Blueprint route handlers that expose the
application's REST API. Each module corresponds to a distinct domain:

- ``auth``: User registration, login, session management, and profile retrieval.
- ``carbon``: Footprint calculation, history retrieval, scenario simulation,
  and AI-powered future predictions.
- ``coach``: AI coaching insights, smart action plans, and goal completion tracking.
- ``analytics``: Telemetry event logging and aggregated usage summary retrieval.

Architecture role: Presentation / controller layer — translates HTTP requests
into service-layer calls and serialises results back to JSON using the shared
response helpers from ``app.utils.response``.
"""

from app.routes.auth import auth_bp, csrf_protect, login_required
from app.routes.analytics import analytics_bp
from app.routes.carbon import carbon_bp
from app.routes.coach import coach_bp

__all__ = [
    "auth_bp",
    "carbon_bp",
    "coach_bp",
    "analytics_bp",
    "login_required",
    "csrf_protect",
]
