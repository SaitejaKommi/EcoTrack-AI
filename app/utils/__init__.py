"""
Utilities Package for CarbonWise AI.

This package contains shared infrastructure helpers that are used across
multiple layers of the application without depending on any single feature:

- ``db_mock``: File-backed in-process document store that mirrors the PyMongo
  Collection API for local development and testing.
- ``response``: Standardised JSON response envelope helpers for Flask route
  handlers, enforcing a consistent API contract.

Architecture role: Cross-cutting infrastructure — consumed by the route layer,
service layer, and test suite. Has no dependencies on other application packages.
"""

from app.utils.db_mock import JSONDatabaseMock
from app.utils.response import (
    error_response,
    service_unavailable_response,
    success_response,
    validation_error_response,
)

__all__ = [
    "JSONDatabaseMock",
    "success_response",
    "error_response",
    "validation_error_response",
    "service_unavailable_response",
]
