from functools import wraps
from flask import Blueprint, request, session, Response
from typing import Tuple, Any, Dict
from app.models.schemas import validate_register, validate_login
from app.utils.response import success_response, error_response
from app.services.user_service import UserService

auth_bp = Blueprint('auth', __name__)

def login_required(f: Any) -> Any:
    """Decorator to enforce session authentication check on API endpoints."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if 'user_id' not in session:
            return error_response("Authentication required. Please log in first.", 401)
        return f(*args, **kwargs)
    return decorated_function

def csrf_protect(f: Any) -> Any:
    """Decorator to enforce Custom Header-based CSRF security on stateful actions."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if request.method in ["POST", "PUT", "DELETE"]:
            if request.headers.get("X-Requested-With") != "XMLHttpRequest":
                return error_response("Security Alert: CSRF request blocked. Verification header missing.", 400)
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/register', methods=['POST'])
@csrf_protect
def register() -> Tuple[Response, int]:
    """Registers a new user profile."""
    # Read request payload
    data = request.get_json(silent=True)
    is_valid, err, cleaned = validate_register(data)
    
    if not is_valid:
        return error_response(err, 400)
        
    success, result = UserService.create_user(cleaned)
    if not success:
        return error_response(result, 400)
        
    return success_response("User registered successfully.", {"user_id": result}, 201)

@auth_bp.route('/login', methods=['POST'])
@csrf_protect
def login() -> Tuple[Response, int]:
    """Logs in an existing user and initiates a session."""
    data = request.get_json(silent=True)
    is_valid, err, cleaned = validate_login(data)
    
    if not is_valid:
        return error_response(err, 400)
        
    user_info = UserService.authenticate_user(cleaned)
    if not user_info:
        return error_response("Invalid email or password combination.", 401)
        
    # Store user identity in encrypted session cookie
    session['user_id'] = user_info['id']
    session['username'] = user_info['username']
    
    return success_response("Login successful.", user_info, 200)

@auth_bp.route('/logout', methods=['POST'])
@csrf_protect
def logout() -> Tuple[Response, int]:
    """Clears the user session."""
    session.clear()
    return success_response("Logged out successfully.", status_code=200)

@auth_bp.route('/profile', methods=['GET'])
@login_required
def get_profile() -> Tuple[Response, int]:
    """Retrieves detailed profile metadata for the authenticated user."""
    user_id = session['user_id']
    profile = UserService.get_user_profile(user_id)
    if not profile:
        return error_response("User profile not found.", 404)
        
    return success_response("Profile retrieved successfully.", profile, 200)
