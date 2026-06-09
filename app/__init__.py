"""
Application Factory Module for CarbonWise AI.

Creates and configures the Flask application using the Application Factory
pattern, which enables instantiation with different configurations for
development, testing, and production without module-level side effects.

Responsibilities:
    - Load configuration from ``Config``.
    - Initialise the database connection (eager preloading to surface errors).
    - Apply Flask-Talisman security headers (CSP, HTTPS enforcement, HSTS).
    - Apply Flask-Limiter rate limiting (100/hour, 10/minute per IP).
    - Register API Blueprint routes under ``/api/*``.
    - Register standardised JSON error handlers for 400/401/403/404/429/500.
    - Serve the single-page application ``index.html`` at the root route.

Architecture role: Infrastructure / composition root — the only place where
all application modules are wired together. Keeps individual modules decoupled
by avoiding circular imports through lazy Blueprint registration.

Typical usage:
    from app import create_app
    app = create_app()
    app.run()
"""

import logging
from typing import Callable, Tuple

from flask import Flask, Response, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from app.config import Config
from app.constants import RATE_LIMIT_HOURLY, RATE_LIMIT_MINUTELY
from app.db import get_db

logger = logging.getLogger(__name__)

# Rate limiter is initialised here to avoid circular imports between the
# factory and individual route modules that may also need limiter decorators.
# ``init_app()`` is called later inside ``create_app()`` after the Flask
# instance exists.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[RATE_LIMIT_HOURLY, RATE_LIMIT_MINUTELY],
)

# Content Security Policy restricts which origins may load scripts, styles,
# fonts, and images. This whitelist keeps the application secure without
# preventing Chart.js, Google Fonts, or Bootstrap Icons from loading.
_CSP: dict = {
    "default-src": "'self'",
    "script-src": [
        "'self'",
        "https://cdn.jsdelivr.net",  # Chart.js and Bootstrap Icons CDN
        "'unsafe-inline'",           # Required for inline Chart.js canvas setup
    ],
    "style-src": [
        "'self'",
        "https://cdn.jsdelivr.net",
        "https://fonts.googleapis.com",
        "'unsafe-inline'",           # Required for HSL theme variables and dark mode
    ],
    "font-src": [
        "'self'",
        "https://fonts.gstatic.com",
        "https://cdn.jsdelivr.net",  # Bootstrap Icons font files
    ],
    "img-src": [
        "'self'",
        "data:",                     # Inline data URIs used by Chart.js for icons
        "https://images.unsplash.com",
    ],
    "connect-src": ["'self'"],
}


def create_app() -> Flask:
    """Create, configure, and return a Flask application instance.

    Implements the Application Factory pattern so that multiple independent
    instances (development server, test client, Gunicorn workers) can each
    create their own app object without shared module-level state causing
    cross-contamination between requests.

    Returns:
        Flask: Fully configured application instance ready to accept requests
        or be passed to a WSGI server.

    Raises:
        No exceptions — configuration errors are logged and handled gracefully
        by enabling fallback modes (mock database, mock AI).
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Load all settings from the Config class into Flask's config dict
    app.config.from_object(Config)

    # Surface any missing credential warnings before handling requests
    Config.validate_and_log()

    # Eagerly initialise the database so connection errors appear at startup
    # rather than on the first incoming request
    with app.app_context():
        get_db()

    limiter.init_app(app)

    _configure_talisman(app)
    _register_blueprints(app)
    _register_index_route(app)
    register_error_handlers(app)

    logger.info("[App] CarbonWise AI application created successfully.")
    return app


def _configure_talisman(app: Flask) -> None:
    """Apply Flask-Talisman security headers to the application.

    Disables HTTPS enforcement and secure cookie flags in development and
    testing environments where TLS is not available. In production, Talisman
    enforces HTTPS, sets HSTS, and applies the full Content Security Policy.

    Args:
        app: The Flask application instance to configure.

    Returns:
        None
    """
    # Determine whether to force HTTPS — disabled for dev/test to avoid
    # certificate errors on localhost
    is_testing = Config.FLASK_ENV == "testing" or app.config.get("TESTING", False)
    disable_ssl = Config.DEBUG or is_testing

    Talisman(
        app,
        content_security_policy=_CSP,
        force_https=not disable_ssl,
        session_cookie_secure=not disable_ssl,
        session_cookie_http_only=True,
    )


def _register_blueprints(app: Flask) -> None:
    """Register all API Blueprint modules with their URL prefixes.

    Blueprints are imported inside this function to avoid circular imports
    between the factory module and route modules that import ``limiter``.

    Args:
        app: The Flask application instance to register blueprints onto.

    Returns:
        None
    """
    from app.routes.analytics import analytics_bp
    from app.routes.auth import auth_bp
    from app.routes.carbon import carbon_bp
    from app.routes.coach import coach_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(carbon_bp, url_prefix="/api/carbon")
    app.register_blueprint(coach_bp, url_prefix="/api/coach")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")


def _register_index_route(app: Flask) -> None:
    """Register the catch-all root route to serve the SPA entry point.

    Args:
        app: The Flask application instance to register the route on.

    Returns:
        None
    """
    @app.route("/")
    def index() -> str:
        """Serve the Single Page Application index template.

        Returns:
            str: Rendered ``index.html`` template content.
        """
        return render_template("index.html")


def register_error_handlers(app: Flask) -> None:
    """Register standardised JSON error handlers for common HTTP error codes.

    All handlers return a consistent ``{"status", "code", "message"}`` envelope
    matching the ``error_response()`` format so API consumers always receive
    predictable JSON regardless of how the error was raised.

    Args:
        app: The Flask application instance to register handlers on.

    Returns:
        None
    """
    @app.errorhandler(400)
    def bad_request(error: Exception) -> Tuple[Response, int]:
        """Handle 400 Bad Request errors with a JSON envelope.

        Args:
            error: The underlying Werkzeug HTTP exception.

        Returns:
            Tuple[Response, int]: JSON error response with status 400.
        """
        description = getattr(error, "description", str(error))
        return jsonify({
            "status": "error",
            "code": 400,
            "message": f"Bad Request: {description}",
        }), 400

    @app.errorhandler(401)
    def unauthorized(error: Exception) -> Tuple[Response, int]:
        """Handle 401 Unauthorized errors with a JSON envelope.

        Args:
            error: The underlying Werkzeug HTTP exception.

        Returns:
            Tuple[Response, int]: JSON error response with status 401.
        """
        return jsonify({
            "status": "error",
            "code": 401,
            "message": "Unauthorized: Access credentials missing or invalid.",
        }), 401

    @app.errorhandler(403)
    def forbidden(error: Exception) -> Tuple[Response, int]:
        """Handle 403 Forbidden errors with a JSON envelope.

        Args:
            error: The underlying Werkzeug HTTP exception.

        Returns:
            Tuple[Response, int]: JSON error response with status 403.
        """
        return jsonify({
            "status": "error",
            "code": 403,
            "message": "Forbidden: You do not have permission to access this resource.",
        }), 403

    @app.errorhandler(404)
    def not_found(error: Exception) -> Tuple[Response, int]:
        """Handle 404 Not Found errors with a JSON envelope.

        Args:
            error: The underlying Werkzeug HTTP exception.

        Returns:
            Tuple[Response, int]: JSON error response with status 404.
        """
        return jsonify({
            "status": "error",
            "code": 404,
            "message": "Not Found: The requested resource could not be found.",
        }), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(error: Exception) -> Tuple[Response, int]:
        """Handle 429 Too Many Requests errors with a JSON envelope.

        Args:
            error: The underlying Flask-Limiter rate limit exception.

        Returns:
            Tuple[Response, int]: JSON error response with status 429.
        """
        return jsonify({
            "status": "error",
            "code": 429,
            "message": "Too Many Requests: Rate limit exceeded. Please try again later.",
        }), 429

    @app.errorhandler(500)
    def internal_server_error(error: Exception) -> Tuple[Response, int]:
        """Handle 500 Internal Server Error with a JSON envelope.

        In debug mode the raw error message is included to assist development.
        In production a generic message is returned to avoid leaking internals.

        Args:
            error: The underlying exception that triggered the 500 response.

        Returns:
            Tuple[Response, int]: JSON error response with status 500.
        """
        # Expose detailed error text only in debug mode to prevent information disclosure
        message = str(error) if Config.DEBUG else "An unexpected error occurred on the server."
        return jsonify({
            "status": "error",
            "code": 500,
            "message": f"Internal Server Error: {message}",
        }), 500
