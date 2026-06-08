"""
API Response Helpers for CarbonWise AI.
Centralizes success and error response formatting structures to enforce DRY principles.
"""

from flask import jsonify, Response
from typing import Any, Tuple

def success_response(message: str = "Success", data: Any = None, status_code: int = 200) -> Tuple[Response, int]:
    """Returns a standardized JSON success response."""
    payload = {
        "status": "success",
        "code": status_code,
        "message": message
    }
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code

def error_response(message: str, status_code: int = 400) -> Tuple[Response, int]:
    """Returns a standardized JSON error response."""
    return jsonify({
        "status": "error",
        "code": status_code,
        "message": message
    }), status_code
