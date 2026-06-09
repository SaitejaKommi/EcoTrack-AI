"""
Models Package for CarbonWise AI.

This package contains input validation schemas used to sanitise and
validate user-supplied data at the API controller boundaries before it
reaches the service layer.

- ``schemas``: Validation functions for registration, login, carbon
  calculator, simulation, and telemetry event payloads.

Architecture role: Data validation layer — sits between raw HTTP request
bodies and the service layer. Guarantees that service functions receive
clean, type-safe, range-checked inputs.
"""

from app.models.schemas import (
    clean_string,
    validate_analytics_event,
    validate_carbon_input,
    validate_login,
    validate_register,
    validate_simulation,
)

__all__ = [
    "clean_string",
    "validate_register",
    "validate_login",
    "validate_carbon_input",
    "validate_simulation",
    "validate_analytics_event",
]
