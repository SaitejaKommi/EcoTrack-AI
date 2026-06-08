"""
Pytest Configuration and Fixtures for CarbonWise AI.
Mocks external network calls (Gemini API, MongoDB) to ensure isolated, repeatable test execution.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Ensure project root is in python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock google generative ai module BEFORE imports occur in app
mock_genai = MagicMock()
sys.modules['google.generativeai'] = mock_genai

# Pre-set mock environment variables
os.environ['SECRET_KEY'] = 'test-secret-key-carbonwise'
os.environ['FLASK_ENV'] = 'testing'
os.environ['MONGO_URI'] = '' # Forces mock fallback
os.environ['GEMINI_API_KEY'] = '' # Forces mock fallback

from app import create_app
from app.db import JSONDatabaseMock

@pytest.fixture(scope="session")
def app():
    """Initializes a Flask app instance in testing configuration."""
    flask_app = create_app()
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-key-talisman-bypass",
    })
    
    @flask_app.route('/test-error/<int:code>')
    def trigger_error(code):
        from flask import abort
        abort(code)
        
    return flask_app

@pytest.fixture(scope="function")
def db_mock():
    """Returns a fresh JSON Database Mock to isolate test transactions."""
    import app.db
    # Reset cached database to prevent cross-test transaction leakages
    app.db._db_instance = None
    
    test_db_path = "test_local_db.json"
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass
            
    mock_db = JSONDatabaseMock(filepath=test_db_path)
    # Cache the mock db instance globally
    app.db._db_instance = mock_db
    
    yield mock_db
        
    # Clean up and reset
    app.db._db_instance = None
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass

@pytest.fixture
def client(app, db_mock):
    """A Flask test client context."""
    return app.test_client()

@pytest.fixture
def auth_client(client):
    """A Flask test client pre-authenticated with a mock user session."""
    with client.session_transaction() as sess:
        sess['user_id'] = 'user123'
        sess['username'] = 'testuser'
    return client
