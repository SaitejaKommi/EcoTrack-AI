"""
Infrastructure and Mock Fallback Tests for CarbonWise AI.
Validates database connection timeouts, mock collection deletions,
and all branches of local AI coaching advice generators.
"""

import pytest
from unittest.mock import patch, MagicMock
from pymongo.errors import ConnectionFailure
from app.db import get_db
from app.utils.db_mock import JSONDatabaseMock
from app.services.gemini_service import GeminiService
from app.config import Config

def test_json_database_mock_deletion():
    """Tests delete_one and count methods inside local JSON Mock DB."""
    db = JSONDatabaseMock(filepath="test_temp_db.json")
    col = db["calculations"]
    
    # Empty count
    assert col.count_documents({}) == 0
    
    # Insert items
    doc1 = {"_id": "1", "score": 90}
    doc2 = {"_id": "2", "score": 80}
    col.insert_one(doc1)
    col.insert_one(doc2)
    assert col.count_documents({}) == 2
    
    # Delete single item
    del_res = col.delete_one({"score": 90})
    assert del_res.deleted_count == 1
    assert col.count_documents({}) == 1
    
    # Cleanup temp db file
    import os
    if os.path.exists("test_temp_db.json"):
        try:
            os.remove("test_temp_db.json")
        except OSError:
            pass

def test_database_connection_failure_fallback():
    """Mocks MongoDB MongoClient ping to fail, verifying graceful fallback to local JSON database."""
    import app.db
    app.db._db_instance = None # Reset cached instance
    
    # Set config to think Atlas is defined
    old_uri = Config.MONGO_URI
    old_mock = Config.MOCK_MODE
    Config.MONGO_URI = "mongodb://localhost:27017"
    Config.MOCK_MODE = False
    
    # Mock MongoClient to raise a connection error when pinged
    with patch("app.db.MongoClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.admin.command.side_effect = ConnectionFailure("Mocked connection failure")
        
        db = get_db()
        # Should fall back to JSON database mock
        assert isinstance(db, JSONDatabaseMock)
        assert Config.MOCK_MODE is True
        
    # Restore config
    Config.MONGO_URI = old_uri
    Config.MOCK_MODE = old_mock
    app.db._db_instance = None # Cleanup

def test_gemini_fallback_branches():
    """Executes all branches inside mock coach advisor to achieve 100% test coverage on fallbacks."""
    
    # Case 1: Commuter with high car miles, high grid usage, and meat heavy diet
    footprint_1 = {
        "emissions": {"transport": 400.0, "energy": 300.0, "food": 270.0, "consumption": 150.0, "total": 1120.0},
        "category_scores": {"transport": 30, "energy": 25, "food": 20, "consumption": 30},
        "eco_score": 26.0,
        "inputs": {
            "transport": {"gas_car_km": 1000.0},
            "energy": {"grid_kwh": 400.0},
            "food": {"diet": "meat_heavy"},
            "consumption": {"shopping_habit": "high_shopper"}
        }
    }
    
    res_1 = GeminiService._get_mock_coaching(
        footprint_1["emissions"],
        footprint_1["category_scores"],
        footprint_1["inputs"]
    )
    assert any("car commuting" in ins for ins in res_1["insights"])
    assert any("Grid-sourced" in ins for ins in res_1["insights"])
    assert any("meat-heavy" in ins for ins in res_1["insights"])

    # Case 2: Transit user with low car miles, low grid usage, and vegan diet
    footprint_2 = {
        "emissions": {"transport": 10.0, "energy": 15.0, "food": 36.0, "consumption": 15.0, "total": 76.0},
        "category_scores": {"transport": 95, "energy": 90, "food": 95, "consumption": 90},
        "eco_score": 93.0,
        "inputs": {
            "transport": {"gas_car_km": 20.0},
            "energy": {"grid_kwh": 50.0},
            "food": {"diet": "vegan"},
            "consumption": {"shopping_habit": "minimalist"}
        }
    }
    
    res_2 = GeminiService._get_mock_coaching(
        footprint_2["emissions"],
        footprint_2["category_scores"],
        footprint_2["inputs"]
    )
    assert any("commuting footprint is relatively light" in ins for ins in res_2["insights"])
    assert any("electricity consumption is efficiently" in ins for ins in res_2["insights"])
    assert any("plant-inclined" in ins for ins in res_2["insights"])

def test_gemini_api_call_success_branch():
    """Tests the real API code paths in GeminiService by patching the genai client."""
    # Configure mock API key temporarily
    old_key = Config.GEMINI_API_KEY
    old_mock = Config.MOCK_MODE
    Config.GEMINI_API_KEY = "dummy_key_for_testing"
    Config.MOCK_MODE = False
    GeminiService._initialized = False # Force re-init
    
    # Create mock response object
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"insights": ["Insight 1", "Insight 2", "Insight 3"], "suggestions": ["S1", "S2", "S3"], "weekly_goals": []}'
    mock_model.generate_content.return_value = mock_response
    
    with patch("google.generativeai.GenerativeModel", return_value=mock_model) as mock_gen_model:
        # Check generate_coaching_insights
        footprint = {
            "emissions": {"transport": 10.0, "energy": 10.0, "food": 10.0, "consumption": 10.0, "total": 40.0},
            "category_scores": {"transport": 90, "energy": 90, "food": 90, "consumption": 90},
            "eco_score": 90.0,
            "inputs": {}
        }
        res = GeminiService.generate_coaching_insights("usr_1", footprint)
        assert "insights" in res
        mock_gen_model.assert_called_with("gemini-1.5-flash")
        
        # Test predict_future_footprint
        mock_response.text = '{"projection_30_days": 150.0, "projection_90_days": 120.0, "reasoning": "Emissions shrinking."}'
        res_pred = GeminiService.predict_future_footprint([footprint])
        assert res_pred["projection_30_days"] == 150.0
        
        # Test generate_action_plan
        mock_response.text = '{"daily": [], "weekly": [], "monthly": []}'
        res_plan = GeminiService.generate_action_plan("usr_1", footprint)
        assert "daily" in res_plan
        
    # Restore configs
    Config.GEMINI_API_KEY = old_key
    Config.MOCK_MODE = old_mock
    GeminiService._initialized = False

def test_gemini_api_call_failure_branch():
    """Tests the fallback routing when Gemini API client raises an exception."""
    # Configure mock API key temporarily
    old_key = Config.GEMINI_API_KEY
    old_mock = Config.MOCK_MODE
    Config.GEMINI_API_KEY = "dummy_key_for_testing"
    Config.MOCK_MODE = False
    GeminiService._initialized = False # Force re-init
    
    mock_model = MagicMock()
    # Force generate_content to raise an exception
    mock_model.generate_content.side_effect = Exception("API connection timed out")
    
    with patch("google.generativeai.GenerativeModel", return_value=mock_model):
        footprint = {
            "emissions": {"transport": 10.0, "energy": 10.0, "food": 10.0, "consumption": 10.0, "total": 40.0},
            "category_scores": {"transport": 90, "energy": 90, "food": 90, "consumption": 90},
            "eco_score": 90.0,
            "inputs": {}
        }
        res = GeminiService.generate_coaching_insights("usr_1", footprint)
        # Should fall back to mock advisor gracefully
        assert "insights" in res
        
    # Restore configs
    Config.GEMINI_API_KEY = old_key
    Config.MOCK_MODE = old_mock
    GeminiService._initialized = False

