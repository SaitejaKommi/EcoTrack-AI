"""
Application Configuration Module for CarbonWise AI.

Loads all runtime configuration from environment variables using
``python-dotenv``. Provides a single ``Config`` class that is consumed
by the Flask application factory and all modules that need runtime
settings (database URI, API keys, server host/port).

Environment Variable Reference:
    SECRET_KEY     — Flask session signing key (required in production).
    FLASK_ENV      — One of ``"development"``, ``"testing"``, or ``"production"``.
    HOST           — Server bind address (default: ``"127.0.0.1"``).
    PORT           — Server listen port (default: ``5000``).
    MONGO_URI      — Full MongoDB Atlas connection string.
    GEMINI_API_KEY — Google Gemini Generative AI API key.

Architecture role: Infrastructure / configuration layer — no business logic.
Imported by ``app/__init__.py`` (factory), ``app/db.py`` (database), and
``app/services/gemini_service.py`` (AI integration).

Typical usage:
    from app.config import Config
    app.config.from_object(Config)
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv

# Resolve and load .env from the project root before reading any os.getenv() calls
load_dotenv()

logger = logging.getLogger(__name__)

# Default server values — kept here rather than in constants.py because they
# are infrastructure concerns rather than business-logic values.
_DEFAULT_HOST: str = "127.0.0.1"
_DEFAULT_PORT: int = 5000
_DEV_FALLBACK_SECRET: str = "default-insecure-dev-key-carbonwise-ai"
_DEFAULT_MONGO_FALLBACK: str = "mongodb://localhost:27017/carbonwise"


class Config:
    """Runtime configuration settings loaded from environment variables.

    All class attributes are set at class-definition time by reading from
    environment variables, making the Config class a lightweight singleton
    without instantiation overhead.

    Attributes:
        SECRET_KEY: Flask session signing key. Must be a long random string
            in production; defaults to an insecure placeholder in development.
        FLASK_ENV: Active environment name — controls debug mode and SSL.
        DEBUG: ``True`` only in the ``"development"`` environment.
        HOST: Server bind interface address.
        PORT: Server listen port number.
        MONGO_URI: Full MongoDB Atlas connection URI, or ``None`` when absent.
        GEMINI_API_KEY: Google Gemini API key, or ``None`` when absent.
        MOCK_MODE: Runtime flag set to ``True`` when any critical service is
            unavailable, causing the application to fall back to local mocks.
    """

    # Flask core settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", _DEV_FALLBACK_SECRET)
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = os.getenv("FLASK_ENV", "development") == "development"

    # Server binding settings
    HOST: str = os.getenv("HOST", _DEFAULT_HOST)
    PORT: int = int(os.getenv("PORT", str(_DEFAULT_PORT)))

    # External service credentials
    MONGO_URI: Optional[str] = os.getenv("MONGO_URI")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")

    # Runtime flag — set to True when falling back to local mock implementations
    MOCK_MODE: bool = False

    @classmethod
    def validate_and_log(cls) -> None:
        """Check critical configuration values and activate fallback modes when absent.

        Logs a warning and sets ``MOCK_MODE = True`` when the Gemini API key
        or MongoDB URI are missing. This prevents silent failures by making the
        application's degraded state explicit in the startup logs.

        When ``MONGO_URI`` is absent, the value is set to a local connection
        string so that the database module receives a non-``None`` value and
        can attempt a local connection before falling back to the JSON mock.

        Returns:
            None

        Raises:
            No exceptions — missing credentials are handled gracefully.
        """
        if not cls.GEMINI_API_KEY or not cls.GEMINI_API_KEY.strip():
            logger.warning(
                "[Config] GEMINI_API_KEY not configured. "
                "CarbonWise AI will run in Mock AI Mode."
            )
            cls.MOCK_MODE = True

        if not cls.MONGO_URI or not cls.MONGO_URI.strip():
            logger.warning(
                "[Config] MONGO_URI not configured. "
                "Falling back to local Mock Database Mode."
            )
            # Assign local fallback so the db module receives a non-None URI
            cls.MONGO_URI = _DEFAULT_MONGO_FALLBACK
            cls.MOCK_MODE = True
