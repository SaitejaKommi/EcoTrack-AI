"""
Application Factory Module for CarbonWise AI.
Configures and initializes Flask integrations including security headers, rate limiting,
routing blueprints, and dynamic database fallbacks.
"""

from flask import Flask, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from app.config import Config
from app.db import get_db

# Initialize Rate Limiter globally (resets count based on IP)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per hour", "10 per minute"]
)

def create_app() -> Flask:
    """
    Creates and configures a Flask application instance.
    Returns:
        Flask: The configured application instance.
    """
    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # Load settings from Config class
    app.config.from_object(Config)
    
    # Validate configuration and detect fallback modes
    Config.validate_and_log()
    
    # Initialize Database connection pool or fallback json-db
    with app.app_context():
        get_db()
    
    # Initialize Rate Limiter
    limiter.init_app(app)
    
    # Setup Content Security Policy (CSP) and Security Headers
    csp = {
        'default-src': "'self'",
        'script-src': [
            "'self'",
            "https://cdn.jsdelivr.net", # Chart.js CDN and icons
            "'unsafe-inline'",         # For dynamic script evaluations if necessary
        ],
        'style-src': [
            "'self'",
            "https://cdn.jsdelivr.net",
            "https://fonts.googleapis.com",
            "'unsafe-inline'"          # For interactive HSL adjustments & themes
        ],
        'font-src': [
            "'self'",
            "https://fonts.gstatic.com",
            "https://cdn.jsdelivr.net"
        ],
        'img-src': [
            "'self'",
            "data:",
            "https://images.unsplash.com" # For user profile placeholders if needed
        ],
        'connect-src': [
            "'self'"
        ]
    }
    
    is_testing = Config.FLASK_ENV == "testing" or app.config.get("TESTING", False)
    disable_ssl = Config.DEBUG or is_testing

    # Enable Talisman with custom CSP, disabling HTTPS enforcement in debug/test modes
    Talisman(
        app,
        content_security_policy=csp,
        force_https=not disable_ssl,
        session_cookie_secure=not disable_ssl,
        session_cookie_http_only=True
    )
    
    # Register API Blueprints
    from app.routes.auth import auth_bp
    from app.routes.carbon import carbon_bp
    from app.routes.coach import coach_bp
    from app.routes.analytics import analytics_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(carbon_bp, url_prefix='/api/carbon')
    app.register_blueprint(coach_bp, url_prefix='/api/coach')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    
    # Catch-all route to serve the Single Page Application index
    @app.route('/')
    def index():
        return render_template('index.html')
    
    # Register global API error handlers
    register_error_handlers(app)
    
    return app

def register_error_handlers(app: Flask) -> None:
    """
    Registers custom error handlers to respond with standard JSON bodies for API routes.
    """
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            "status": "error",
            "code": 400,
            "message": "Bad Request: " + getattr(error, 'description', str(error))
        }), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            "status": "error",
            "code": 401,
            "message": "Unauthorized: Access credentials missing or invalid."
        }), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            "status": "error",
            "code": 403,
            "message": "Forbidden: You do not have permission to access this resource."
        }), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "status": "error",
            "code": 404,
            "message": "Not Found: The requested resource could not be found."
        }), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({
            "status": "error",
            "code": 429,
            "message": "Too Many Requests: Rate limit exceeded. Please try again later."
        }), 429

    @app.errorhandler(500)
    def internal_server_error(error):
        # In development we can report the trace; in production return a generic message
        message = str(error) if Config.DEBUG else "An unexpected error occurred on the server."
        return jsonify({
            "status": "error",
            "code": 500,
            "message": f"Internal Server Error: {message}"
        }), 500
