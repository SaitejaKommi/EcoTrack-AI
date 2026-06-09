"""
Services Package for CarbonWise AI.

This package contains the application's business logic service classes.
Each service handles one distinct domain concern and communicates with the
data layer through the ``get_db()`` function from ``app.db``:

- ``carbon_service``: Carbon emission calculations, Eco Score computation,
  simulation scenarios, and badge eligibility evaluation.
- ``user_service``: User registration, credential authentication, profile
  retrieval, activity streak management, and badge awards.
- ``gemini_service``: Google Gemini API integration for personalised coaching
  insights, future footprint predictions, and smart action plan generation.
- ``analytics_service``: Telemetry event logging and aggregated usage
  statistics retrieval.

Architecture role: Business logic layer — sits between the route controllers
and the database. Route handlers must not contain business logic; all
computation is delegated to these services.
"""

from app.services.analytics_service import AnalyticsService
from app.services.carbon_service import CarbonService
from app.services.gemini_service import GeminiService
from app.services.user_service import UserService

__all__ = [
    "CarbonService",
    "UserService",
    "GeminiService",
    "AnalyticsService",
]
