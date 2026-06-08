"""
Validation Schema Edge-Case Tests for CarbonWise AI.
Validates input sanitizers, numeric conversions, and error pathways in schemas.py.
"""

import pytest
from app.models.schemas import (
    validate_register,
    validate_login,
    validate_carbon_input,
    validate_simulation,
    validate_analytics_event,
    clean_string
)

def test_string_sanitizer():
    """Verifies that clean_string strips HTML and script tags."""
    assert clean_string("hello <b>world</b>") == "hello world"
    assert clean_string("<script>alert(1)</script>test") == "alert(1)test"
    assert clean_string(123) == ""

def test_validation_register_failures():
    """Tests bad payloads inside register validator."""
    # Empty payload
    is_v, err, _ = validate_register(None)
    assert is_v is False
    
    # Username too short
    is_v, err, _ = validate_register({"username": "ab", "email": "ok@test.com", "password": "123"})
    assert is_v is False
    assert "Username" in err

    # Bad email
    is_v, err, _ = validate_register({"username": "tester", "email": "bademail", "password": "123"})
    assert is_v is False
    assert "email" in err.lower()

    # Password too short
    is_v, err, _ = validate_register({"username": "tester", "email": "ok@test.com", "password": "123"})
    assert is_v is False
    assert "Password" in err

def test_validation_login_failures():
    """Tests login validation edge-cases."""
    is_v, err, _ = validate_login(None)
    assert is_v is False
    
    is_v, err, _ = validate_login({"email": ""})
    assert is_v is False
    
    is_v, err, _ = validate_login({"email": "test@test.com", "password": ""})
    assert is_v is False

def test_validation_carbon_failures():
    """Tests carbon calculation validation errors."""
    is_v, err, _ = validate_carbon_input(None)
    assert is_v is False
    
    is_v, err, _ = validate_carbon_input({"transport": "not_a_dict"})
    assert is_v is False
    
    is_v, err, _ = validate_carbon_input({"transport": {}, "energy": "not_a_dict"})
    assert is_v is False
    
    # Invalid diet option
    is_v, err, _ = validate_carbon_input({
        "transport": {},
        "energy": {},
        "food": {"diet": "meat_heavy_extreme"},
        "consumption": {}
    })
    assert is_v is False
    assert "diet" in err.lower()

    # Invalid shopping option
    is_v, err, _ = validate_carbon_input({
        "transport": {},
        "energy": {},
        "food": {"diet": "vegan"},
        "consumption": {"shopping_habit": "super_shopper"}
    })
    assert is_v is False
    assert "shopping" in err.lower()

    # Numeric formatting errors
    is_v, err, _ = validate_carbon_input({
        "transport": {"gas_car_km": "invalid_number"},
        "energy": {},
        "food": {"diet": "vegan"},
        "consumption": {"shopping_habit": "minimalist"}
    })
    assert is_v is False

def test_validation_simulation_failures():
    """Tests simulator parameters boundary validation."""
    is_v, err, _ = validate_simulation(None)
    assert is_v is False
    
    # Non-numeric ranges
    is_v, err, _ = validate_simulation({"public_transit_shift": "invalid"})
    assert is_v is False
    
    # Base footprint validation errors
    is_v, err, _ = validate_simulation({
        "public_transit_shift": 50,
        "meat_reduction": 20,
        "clean_energy_shift": 10,
        "base_footprint": {"transport": "bad_type"}
    })
    assert is_v is False

def test_validation_analytics_failures():
    """Tests analytics event checks."""
    is_v, err, _ = validate_analytics_event(None)
    assert is_v is False
    
    # Missing type
    is_v, err, _ = validate_analytics_event({"metadata": {}})
    assert is_v is False
    
    # Metadata is not dict
    is_v, err, _ = validate_analytics_event({"event_type": "calculator_submitted", "metadata": "string"})
    assert is_v is False
    
    # Unallowed event type
    is_v, err, _ = validate_analytics_event({"event_type": "button_clicked", "metadata": {}})
    assert is_v is False
