"""
API Response Helpers for CarbonWise AI.

Centralises every JSON response shape returned by route handlers into a
single module to enforce DRY principles and consistent API contracts. All
route blueprints must import from this module rather than calling
``jsonify()`` directly.

Architecture role: Presentation utility layer — sits between the route
handlers and the Flask JSON serialiser. Keeps response envelope structure
uniform across every endpoint so that API consumers always receive a
predictable ``{"status", "code", "message", "data"}`` envelope.

Typical usage:
    from app.utils.response import success_response, error_response
    return success_response("Calculation saved.", result, 200)
    return error_response("Invalid input.", 400)
"""

from typing import Any, Dict, List, Optional, Tuple

from flask import Response, jsonify


def success_response(
    message: str = "Success",
    data: Any = None,
    status_code: int = 200,
) -> Tuple[Response, int]:
    """Build a standardised JSON success response envelope.

    Args:
        message: Human-readable description of the operation result.
            Defaults to ``"Success"``.
        data: Optional payload to embed under the ``"data"`` key.
            Omitted from the envelope when ``None``.
        status_code: HTTP status code to return. Defaults to ``200``.

    Returns:
        Tuple[Response, int]: Flask ``Response`` object and the integer
        HTTP status code, ready to be returned directly from a route handler.
    """
    payload: Dict[str, Any] = {
        "status": "success",
        "code": status_code,
        "message": message,
    }
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code


def error_response(
    message: str,
    status_code: int = 400,
) -> Tuple[Response, int]:
    """Build a standardised JSON error response envelope.

    Args:
        message: Human-readable description of the error condition.
        status_code: HTTP status code to return. Defaults to ``400``.

    Returns:
        Tuple[Response, int]: Flask ``Response`` object and the integer
        HTTP status code, ready to be returned directly from a route handler.
    """
    return (
        jsonify(
            {
                "status": "error",
                "code": status_code,
                "message": message,
            }
        ),
        status_code,
    )


def validation_error_response(
    field: str,
    message: str,
) -> Tuple[Response, int]:
    """Build a standardised 400 response specifically for field-level validation failures.

    Adds a ``"field"`` key to the envelope so that API consumers can
    highlight the offending form control without parsing the message string.

    Args:
        field: Name of the input field that failed validation (e.g.
            ``"email"``, ``"gas_car_km"``).
        message: Human-readable description of the validation failure.

    Returns:
        Tuple[Response, int]: Flask ``Response`` object with status ``400``.
    """
    return (
        jsonify(
            {
                "status": "error",
                "code": 400,
                "field": field,
                "message": message,
            }
        ),
        400,
    )


def service_unavailable_response(service_name: str) -> Tuple[Response, int]:
    """Build a standardised 503 response for when an upstream service is unreachable.

    Args:
        service_name: Human-readable name of the unavailable service (e.g.
            ``"Gemini AI"``, ``"MongoDB Atlas"``).

    Returns:
        Tuple[Response, int]: Flask ``Response`` object with status ``503``.
    """
    return (
        jsonify(
            {
                "status": "error",
                "code": 503,
                "message": f"{service_name} is temporarily unavailable. Please try again later.",
            }
        ),
        503,
    )
