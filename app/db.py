"""
Database Management Module for CarbonWise AI.

Configures the active database backend by attempting a MongoDB Atlas
connection and automatically falling back to a lightweight thread-safe
JSON file-based mock when Atlas is unavailable or unconfigured.

This module is the single entry point for all database access in the
application. Services call ``get_db()`` and receive either a live PyMongo
database handle or the JSONDatabaseMock, both of which expose an identical
PyMongo-compatible collection API.

Architecture role: Infrastructure layer — sits between the service layer
and the physical data store. Implements thread-safe singleton instantiation
to prevent redundant connection attempts across concurrent requests.

Typical usage:
    from app.db import get_db
    db = get_db()
    user = db["users"].find_one({"email": email})
"""

import logging
import threading
from typing import Any

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError

from app.config import Config
from app.utils.db_mock import JSONDatabaseMock

# Module-level logger — avoids bare print() calls in library code
logger = logging.getLogger(__name__)

# ─── Singleton State ──────────────────────────────────────────────────────────
# Global database handle shared across all requests.
_db_instance: Any = None

# Reentrant lock ensures only one thread initialises the connection.
_lock = threading.Lock()

# Connection timeout in milliseconds — prevents slow Atlas handshakes from
# blocking the application startup thread for longer than necessary.
_MONGO_TIMEOUT_MS: int = 2_000

# Default database name used when the URI does not contain a path segment.
_DEFAULT_DB_NAME: str = "carbonwise"


def get_db() -> Any:
    """Return the active database connection, initialising it on first call.

    Implements a thread-safe lazy singleton pattern. On the first invocation
    the function attempts to connect to MongoDB Atlas using the URI stored in
    ``Config.MONGO_URI``. If the connection succeeds the live PyMongo database
    handle is cached and returned on every subsequent call. If Atlas is
    unreachable, or if ``Config.MOCK_MODE`` is set, the function falls back to
    ``JSONDatabaseMock`` — a file-backed in-process store that exposes the same
    collection API as PyMongo.

    Returns:
        Any: Either a live ``pymongo.database.Database`` instance when Atlas is
        reachable, or a ``JSONDatabaseMock`` instance for offline/test operation.
        Both expose the same ``db["collection"]`` subscription interface.

    Raises:
        No exceptions are raised; all connection failures are caught internally
        and result in a silent fallback to the JSON mock store.
    """
    global _db_instance
    with _lock:
        if _db_instance is not None:
            return _db_instance

        mongo_uri = Config.MONGO_URI

        # Use mock immediately when MOCK_MODE is enabled or no URI is supplied
        if Config.MOCK_MODE or not mongo_uri:
            logger.info("[DB] Initialising local JSON database fallback (mock mode).")
            _db_instance = JSONDatabaseMock()
            return _db_instance

        _db_instance = _connect_to_mongo(mongo_uri)
        return _db_instance


def _connect_to_mongo(mongo_uri: str) -> Any:
    """Attempt a MongoDB Atlas connection and fall back to the mock on failure.

    Extracts the database name from the URI path segment, performs a ``ping``
    to verify connectivity, and returns the live database handle. Any exception
    during this process triggers a graceful fallback to ``JSONDatabaseMock``
    with ``Config.MOCK_MODE`` set to ``True`` to prevent repeated connection
    attempts.

    Args:
        mongo_uri: Full MongoDB connection string including credentials,
            cluster host, and optional database name path segment.

    Returns:
        Any: A live ``pymongo.database.Database`` on success, or a
        ``JSONDatabaseMock`` instance on failure.
    """
    try:
        logger.info("[DB] Attempting connection to MongoDB Atlas...")
        # Short timeouts prevent the connection attempt from hanging the startup
        # thread when Atlas is temporarily unreachable.
        client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=_MONGO_TIMEOUT_MS,
            connectTimeoutMS=_MONGO_TIMEOUT_MS,
        )
        # Force an immediate network round-trip to validate the connection
        client.admin.command("ping")

        db_name = _extract_db_name(mongo_uri)
        logger.info("[DB] Successfully connected to MongoDB — database: %s", db_name)
        return client[db_name]

    except (ConnectionFailure, ConfigurationError, Exception) as exc:
        logger.error(
            "[DB] MongoDB connection failed (%s). Activating JSON fallback.", exc
        )
        Config.MOCK_MODE = True
        return JSONDatabaseMock()


def _extract_db_name(mongo_uri: str) -> str:
    """Parse the database name from a MongoDB connection URI.

    Splits on the double-slash authority separator and takes the last path
    segment, stripping any query-string parameters.

    Args:
        mongo_uri: Full MongoDB connection string.

    Returns:
        str: Database name extracted from the URI, or the default name
        ``"carbonwise"`` when no path segment is present.
    """
    # URI structure: mongodb+srv://user:pass@cluster.mongodb.net/dbname?options
    # Split on "://" to isolate the authority+path component, then take the
    # last "/" segment which contains the database name (and optional "?…").
    db_name = mongo_uri.split("/")[-1] if "/" in mongo_uri.split("//")[-1] else _DEFAULT_DB_NAME
    # Remove query-string parameters that follow "?"
    if "?" in db_name:
        db_name = db_name.split("?")[0]
    return db_name or _DEFAULT_DB_NAME
