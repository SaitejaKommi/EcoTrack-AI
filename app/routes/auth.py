"""
Authentication Blueprint for CarbonWise AI.

Handles user registration, login, logout, and profile retrieval. This module
also exports the ``login_required`` and ``csrf_protect`` security decorators
that are applied by every other Blueprint in the application.

CSRF Protection Strategy:
    Custom Header CSRF — every stateful POST/PUT/DELETE request must include
    the ``X-Requested-With: XMLHttpRequest`` header. The frontend JavaScript
    layer attaches this header automatically, while cross-origin form-post
    attacks from other domains cannot set custom headers, making them
    effectively blocked without a CSRF token database.

Session Strategy:
    Sessions are stored in Flask's signed cookie using ``SECRET_KEY``. The
    session contains only ``user_id`` and ``username``; no sensitive data
    is kept on the client side.

Architecture role: Presentation / controller layer — translates HTTP
requests into UserService calls and returns standardised JSON envelopes.
"""

from functools import wraps
from typing import Any, Callable, Tuple

from flask import Blueprint, Response, request, session

from app.models.schemas import validate_login, validate_register
from app.services.user_service import UserService
from app.utils.response import error_response, success_response

auth_bp = Blueprint("auth", __name__)


def login_required(func: Callable) -> Callable:
    """Decorator that blocks unauthenticated access to route handlers.

    Checks for the presence of ``"user_id"`` in the encrypted Flask session
    cookie. Returns a 401 JSON error when the key is absent so that the
    frontend can redirect to the login view.

    Args:
        func: The route handler function being decorated.

    Returns:
        Callable: Wrapped function that checks authentication before
        delegating to the original handler.
    """
    @wraps(func)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            return error_response("Authentication required. Please log in first.", 401)
        return func(*args, **kwargs)

    return decorated_function


def csrf_protect(func: Callable) -> Callable:
    """Decorator that blocks stateful requests missing the CSRF verification header.

    Enforces the custom-header CSRF pattern: every POST, PUT, and DELETE
    request must include ``X-Requested-With: XMLHttpRequest``. Browser-initiated
    cross-origin form posts cannot set this non-standard header, providing
    effective CSRF protection without a synchroniser token.

    Args:
        func: The route handler function being decorated.

    Returns:
        Callable: Wrapped function that validates the CSRF header before
        delegating to the original handler.
    """
    @wraps(func)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if request.method in {"POST", "PUT", "DELETE"}:
            if request.headers.get("X-Requested-With") != "XMLHttpRequest":
                return error_response(
                    "Security Alert: CSRF request blocked. Verification header missing.",
                    400,
                )
        return func(*args, **kwargs)

    return decorated_function


@auth_bp.route("/register", methods=["POST"])
@csrf_protect
def register() -> Tuple[Response, int]:
    """Register a new user account and persist hashed credentials.

    Validates the JSON payload through ``validate_register()``, delegates
    account creation to ``UserService.create_user()``, and returns the
    generated user ID in the success envelope.

    Returns:
        Tuple[Response, int]: 201 with ``{"user_id": str}`` on success,
        400 with a validation or duplication error message on failure.
    """
    data = request.get_json(silent=True)
    is_valid, err, cleaned = validate_register(data)

    if not is_valid:
        return error_response(err, 400)

    success, result = UserService.create_user(cleaned)
    if not success:
        return error_response(result, 400)

    return success_response("User registered successfully.", {"user_id": result}, 201)


@auth_bp.route("/login", methods=["POST"])
@csrf_protect
def login() -> Tuple[Response, int]:
    """Authenticate an existing user and initialise a signed session cookie.

    Validates credentials through ``UserService.authenticate_user()``. On
    success, the user's ID and display name are stored in the Flask session
    so that protected routes can identify the caller without re-querying the
    database on every request.

    Returns:
        Tuple[Response, int]: 200 with full user profile on success,
        400 for invalid payload, 401 for bad credentials.
    """
    data = request.get_json(silent=True)
    is_valid, err, cleaned = validate_login(data)

    if not is_valid:
        return error_response(err, 400)

    user_info = UserService.authenticate_user(cleaned)
    if not user_info:
        return error_response("Invalid email or password combination.", 401)

    # Persist identity in the encrypted Flask session cookie
    session["user_id"] = user_info["id"]
    session["username"] = user_info["username"]

    return success_response("Login successful.", user_info, 200)


@auth_bp.route("/logout", methods=["POST"])
@csrf_protect
def logout() -> Tuple[Response, int]:
    """Clear the active user session to log out.

    Calls ``session.clear()`` which removes all keys from the Flask session
    cookie and forces subsequent requests to be treated as unauthenticated.

    Returns:
        Tuple[Response, int]: 200 with a success message.
    """
    session.clear()
    return success_response("Logged out successfully.", status_code=200)


@auth_bp.route("/profile", methods=["GET"])
@login_required
def get_profile() -> Tuple[Response, int]:
    """Retrieve the authenticated user's profile including streak and badges.

    Reads the ``user_id`` from the session and delegates to
    ``UserService.get_user_profile()`` which returns a sanitised profile
    document with sensitive fields stripped.

    Returns:
        Tuple[Response, int]: 200 with the profile document on success,
        404 when the user record cannot be located in the database.
    """
    user_id = session["user_id"]
    profile = UserService.get_user_profile(user_id)

    if not profile:
        return error_response("User profile not found.", 404)

    return success_response("Profile retrieved successfully.", profile, 200)
