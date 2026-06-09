"""
Validation Schemas for CarbonWise AI.

Provides input sanitisation and validation functions for every user-supplied
payload handled by the API. All validation is applied at the controller
boundary so that service-layer functions receive clean, type-safe, and
range-checked data.

Each validator returns a three-tuple ``(is_valid, error_message, cleaned_data)``
which allows route handlers to respond with a descriptive error or proceed with
a guaranteed-safe payload without writing repetitive try/except blocks.

Architecture role: Data validation layer — no business logic, no database
calls. Pure input sanitisation and schema enforcement.

Typical usage:
    from app.models.schemas import validate_carbon_input
    is_valid, err, cleaned = validate_carbon_input(request.get_json())
    if not is_valid:
        return error_response(err, 400)
"""

import re
from typing import Any, Dict, Optional, Tuple

from app.constants import (
    EMAIL_MAX_LENGTH,
    ENERGY_KWH_MAX_LIMIT,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    TRANSPORT_KM_MAX_LIMIT,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
)


def clean_string(val: Any) -> str:
    """Strip HTML tags and leading/trailing whitespace from a string value.

    Used at every boundary where user-supplied text is accepted to prevent
    stored XSS through tag injection.

    Args:
        val: Value to sanitise. Non-string inputs are treated as empty strings
            rather than raising an exception.

    Returns:
        str: Sanitised string with all ``<tag>`` sequences removed and
        surrounding whitespace trimmed. Returns ``""`` for non-string inputs.
    """
    if not isinstance(val, str):
        return ""
    # Regex removes any sequence starting with "<" and ending with ">" —
    # this covers both opening and closing HTML/script tags.
    cleaned = re.sub(r"<[^>]*>", "", val)
    return cleaned.strip()


def validate_register(
    data: Optional[Dict[str, Any]]
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validate user registration payload with length and format constraints.

    Sanitises all string fields before applying boundary checks. Email is
    normalised to lowercase to ensure case-insensitive uniqueness queries work
    correctly in the database layer.

    Args:
        data: Raw JSON body from the registration request. May be ``None``
            when the request body is missing or malformed.

    Returns:
        Tuple[bool, Optional[str], Dict[str, Any]]:
            - ``is_valid``: ``True`` when all fields pass validation.
            - ``error_message``: Human-readable description of the first
              failure, or ``None`` when valid.
            - ``cleaned_data``: Sanitised payload ready for the service layer,
              or ``{}`` when validation failed.

    Raises:
        No exceptions — all error conditions are returned as the error tuple.
    """
    if not data:
        return False, "Request body cannot be empty", {}

    username = clean_string(data.get("username", ""))
    email = clean_string(data.get("email", ""))
    password = data.get("password", "")

    if not username or len(username) < USERNAME_MIN_LENGTH or len(username) > USERNAME_MAX_LENGTH:
        return (
            False,
            f"Username must be between {USERNAME_MIN_LENGTH} and {USERNAME_MAX_LENGTH} characters long",
            {},
        )

    if not email or "@" not in email or "." not in email or len(email) > EMAIL_MAX_LENGTH:
        return (
            False,
            f"A valid email address (maximum {EMAIL_MAX_LENGTH} characters) is required",
            {},
        )

    if not isinstance(password, str) or len(password) < PASSWORD_MIN_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
        return (
            False,
            f"Password must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters long",
            {},
        )

    return True, None, {
        "username": username,
        "email": email.lower(),
        "password": password,
    }


def validate_login(
    data: Optional[Dict[str, Any]]
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validate login credential payload with length boundaries.

    Args:
        data: Raw JSON body from the login request. May be ``None`` when the
            request body is missing or malformed.

    Returns:
        Tuple[bool, Optional[str], Dict[str, Any]]:
            - ``is_valid``: ``True`` when both fields pass validation.
            - ``error_message``: Description of the first failure, or ``None``.
            - ``cleaned_data``: Sanitised credentials, or ``{}`` on failure.

    Raises:
        No exceptions — all error conditions are returned as the error tuple.
    """
    if not data:
        return False, "Request body cannot be empty", {}

    email = clean_string(data.get("email", ""))
    password = data.get("password", "")

    if not email or len(email) > EMAIL_MAX_LENGTH:
        return (
            False,
            f"A valid email address (maximum {EMAIL_MAX_LENGTH} characters) is required",
            {},
        )

    if not password or len(password) > PASSWORD_MAX_LENGTH:
        return (
            False,
            f"Password (maximum {PASSWORD_MAX_LENGTH} characters) is required",
            {},
        )

    return True, None, {
        "email": email.lower(),
        "password": password,
    }


def validate_carbon_input(
    data: Optional[Dict[str, Any]]
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validate and sanitise a carbon footprint calculator payload.

    Checks that all category sub-objects are dicts, that enumerable fields
    contain recognised values, and that numeric inputs fall within safe
    upper-bound limits. All numeric values are clamped to zero or above to
    prevent negative-emission exploits.

    Args:
        data: Raw JSON body from a calculator submission. May be ``None``.

    Returns:
        Tuple[bool, Optional[str], Dict[str, Any]]:
            - ``is_valid``: ``True`` when the entire payload passes validation.
            - ``error_message``: Description of the first failure, or ``None``.
            - ``cleaned_data``: Fully typed and sanitised calculator inputs
              ready for ``CarbonService``, or ``{}`` on failure.

    Raises:
        No exceptions — all error conditions are returned as the error tuple.
    """
    if not data:
        return False, "Calculator inputs cannot be empty", {}

    transport = data.get("transport", {})
    if not isinstance(transport, dict):
        return False, "Transport inputs must be an object", {}

    energy = data.get("energy", {})
    if not isinstance(energy, dict):
        return False, "Energy inputs must be an object", {}

    food = data.get("food", {})
    if not isinstance(food, dict):
        return False, "Food inputs must be an object", {}

    diet = clean_string(food.get("diet", "balanced"))
    valid_diets = ["meat_heavy", "balanced", "vegetarian", "vegan"]
    if diet not in valid_diets:
        return False, f"Invalid diet choice. Must be one of {valid_diets}", {}

    consumption = data.get("consumption", {})
    if not isinstance(consumption, dict):
        return False, "Consumption inputs must be an object", {}

    shopping = clean_string(consumption.get("shopping_habit", "average_shopper"))
    valid_shopping = ["high_shopper", "average_shopper", "minimalist"]
    if shopping not in valid_shopping:
        return False, f"Invalid shopping choice. Must be one of {valid_shopping}", {}

    cleaned_transport, cleaned_energy, parse_error = _parse_numeric_inputs(transport, energy)
    if parse_error:
        return False, parse_error, {}

    overflow_error = _check_range_limits(cleaned_transport, cleaned_energy)
    if overflow_error:
        return False, overflow_error, {}

    return True, None, {
        "transport": cleaned_transport,
        "energy": cleaned_energy,
        "food": {"diet": diet},
        "consumption": {"shopping_habit": shopping},
    }


def _parse_numeric_inputs(
    transport: Dict[str, Any],
    energy: Dict[str, Any],
) -> Tuple[Dict[str, float], Dict[str, float], Optional[str]]:
    """Parse and clamp transport and energy numeric fields.

    Converts all string or int values to floats and clamps them to zero or
    above, preventing negative-emission inputs without raising exceptions.

    Args:
        transport: Raw transport sub-object from the request body.
        energy: Raw energy sub-object from the request body.

    Returns:
        Tuple[Dict[str, float], Dict[str, float], Optional[str]]:
            - Cleaned transport dict with float values >= 0.
            - Cleaned energy dict with float values >= 0.
            - Error message string if parsing failed, or ``None`` on success.
    """
    try:
        cleaned_transport = {
            "gas_car_km": max(0.0, float(transport.get("gas_car_km", 0.0))),
            "electric_car_km": max(0.0, float(transport.get("electric_car_km", 0.0))),
            "public_transit_km": max(0.0, float(transport.get("public_transit_km", 0.0))),
            "flight_km": max(0.0, float(transport.get("flight_km", 0.0))),
        }
        cleaned_energy = {
            "grid_kwh": max(0.0, float(energy.get("grid_kwh", 0.0))),
            "clean_kwh": max(0.0, float(energy.get("clean_kwh", 0.0))),
        }
    except (ValueError, TypeError):
        return {}, {}, "Calculator numeric parameters must be valid positive numbers"

    return cleaned_transport, cleaned_energy, None


def _check_range_limits(
    cleaned_transport: Dict[str, float],
    cleaned_energy: Dict[str, float],
) -> Optional[str]:
    """Check that numeric inputs do not exceed maximum allowed limits.

    Enforces upper-bound security constraints to prevent overflow or DoS
    payloads from being processed by the emission calculation engine.

    Args:
        cleaned_transport: Parsed transport values with float values >= 0.
        cleaned_energy: Parsed energy values with float values >= 0.

    Returns:
        Optional[str]: An error message when any value exceeds its limit,
        or ``None`` when all values are within safe bounds.
    """
    # Transport values must not exceed TRANSPORT_KM_MAX_LIMIT km per month
    for key, val in cleaned_transport.items():
        if val > TRANSPORT_KM_MAX_LIMIT:
            return (
                f"Transit parameter '{key}' exceeds the maximum allowed logging "
                f"limit ({TRANSPORT_KM_MAX_LIMIT:,.0f} km/mo)"
            )

    # Energy values must not exceed ENERGY_KWH_MAX_LIMIT kWh per month
    for key, val in cleaned_energy.items():
        if val > ENERGY_KWH_MAX_LIMIT:
            return (
                f"Energy parameter '{key}' exceeds the maximum allowed logging "
                f"limit ({ENERGY_KWH_MAX_LIMIT:,.0f} kWh/mo)"
            )

    return None


def validate_simulation(
    data: Optional[Dict[str, Any]]
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validate a lifestyle scenario simulation payload.

    Clamps shift percentages to the [0, 100] range and delegates base
    footprint validation to ``validate_carbon_input``.

    Args:
        data: Raw JSON body from a simulation request. May be ``None``.

    Returns:
        Tuple[bool, Optional[str], Dict[str, Any]]:
            - ``is_valid``: ``True`` when all fields are valid.
            - ``error_message``: Description of the first failure, or ``None``.
            - ``cleaned_data``: Sanitised simulation parameters, or ``{}`` on failure.

    Raises:
        No exceptions — all error conditions are returned as the error tuple.
    """
    if not data:
        return False, "Simulation options cannot be empty", {}

    try:
        # Clamp each shift percentage to the valid [0, 100] range
        public_transit_shift = max(0.0, min(100.0, float(data.get("public_transit_shift", 0.0))))
        meat_reduction = max(0.0, min(100.0, float(data.get("meat_reduction", 0.0))))
        clean_energy_shift = max(0.0, min(100.0, float(data.get("clean_energy_shift", 0.0))))

        is_base_valid, base_err, base_cleaned = validate_carbon_input(data.get("base_footprint"))
        if not is_base_valid:
            return False, f"Invalid baseline footprint reference: {base_err}", {}

    except (ValueError, TypeError) as exc:
        return False, f"Invalid numeric parameters in simulator constraints: {exc}", {}

    return True, None, {
        "public_transit_shift": public_transit_shift,
        "meat_reduction": meat_reduction,
        "clean_energy_shift": clean_energy_shift,
        "base_footprint": base_cleaned,
    }


def validate_analytics_event(
    data: Optional[Dict[str, Any]]
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validate a frontend telemetry event payload.

    Ensures the event type is one of the allowed enumerated values to prevent
    arbitrary event names from polluting the analytics collection.

    Args:
        data: Raw JSON body from an analytics event request. May be ``None``.

    Returns:
        Tuple[bool, Optional[str], Dict[str, Any]]:
            - ``is_valid``: ``True`` when the event type is recognised.
            - ``error_message``: Description of the first failure, or ``None``.
            - ``cleaned_data``: Validated event payload, or ``{}`` on failure.

    Raises:
        No exceptions — all error conditions are returned as the error tuple.
    """
    if not data:
        return False, "Analytics payload cannot be empty", {}

    event_type = clean_string(data.get("event_type", ""))
    metadata = data.get("metadata", {})

    if not event_type:
        return False, "Event type is a required parameter", {}

    if not isinstance(metadata, dict):
        return False, "Telemetry metadata must be an object", {}

    allowed_events = [
        "calculator_submitted",
        "goal_completed",
        "simulation_run",
        "ai_recommendation_accepted",
    ]
    if event_type not in allowed_events:
        return False, f"Event type must be one of {allowed_events}", {}

    return True, None, {
        "event_type": event_type,
        "metadata": metadata,
    }
