"""
Validation Schemas and Utilities for CarbonWise AI.
Responsible for sanitizing and validating user inputs at the API controller boundaries.
"""

import re
from typing import Dict, Any, Tuple, Optional

def clean_string(val: Any) -> str:
    """Removes HTML tags and potential script injections from input strings."""
    if not isinstance(val, str):
        return ""
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]*>', '', val)
    return cleaned.strip()

def validate_register(data: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validates user registration input with length boundaries.
    """
    if not data:
        return False, "Request body cannot be empty", {}

    username = clean_string(data.get("username", ""))
    email = clean_string(data.get("email", ""))
    password = data.get("password", "")

    if not username or len(username) < 3 or len(username) > 30:
        return False, "Username must be between 3 and 30 characters long", {}
    
    if not email or "@" not in email or "." not in email or len(email) > 60:
        return False, "A valid email address (maximum 60 characters) is required", {}
    
    if not isinstance(password, str) or len(password) < 6 or len(password) > 100:
        return False, "Password must be between 6 and 100 characters long", {}

    return True, None, {
        "username": username,
        "email": email.lower(),
        "password": password
    }

def validate_login(data: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validates login credentials with length boundaries.
    """
    if not data:
        return False, "Request body cannot be empty", {}

    email = clean_string(data.get("email", ""))
    password = data.get("password", "")

    if not email or len(email) > 60:
        return False, "A valid email address (maximum 60 characters) is required", {}
    
    if not password or len(password) > 100:
        return False, "Password (maximum 100 characters) is required", {}

    return True, None, {
        "email": email.lower(),
        "password": password
    }

def validate_carbon_input(data: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validates carbon footprint calculator input data with upper limits.
    """
    if not data:
        return False, "Calculator inputs cannot be empty", {}

    # Validate Transport
    transport = data.get("transport", {})
    if not isinstance(transport, dict):
        return False, "Transport inputs must be an object", {}
    
    # Validate Energy
    energy = data.get("energy", {})
    if not isinstance(energy, dict):
        return False, "Energy inputs must be an object", {}

    # Validate Food
    food = data.get("food", {})
    if not isinstance(food, dict):
        return False, "Food inputs must be an object", {}
    diet = clean_string(food.get("diet", "balanced"))
    valid_diets = ["meat_heavy", "balanced", "vegetarian", "vegan"]
    if diet not in valid_diets:
        return False, f"Invalid diet choice. Must be one of {valid_diets}", {}

    # Validate Consumption
    consumption = data.get("consumption", {})
    if not isinstance(consumption, dict):
        return False, "Consumption inputs must be an object", {}
    shopping = clean_string(consumption.get("shopping_habit", "average_shopper"))
    valid_shopping = ["high_shopper", "average_shopper", "minimalist"]
    if shopping not in valid_shopping:
        return False, f"Invalid shopping choice. Must be one of {valid_shopping}", {}

    # Clean and parse numeric bounds safely
    try:
        cleaned_transport = {
            "gas_car_km": max(0.0, float(transport.get("gas_car_km", 0.0))),
            "electric_car_km": max(0.0, float(transport.get("electric_car_km", 0.0))),
            "public_transit_km": max(0.0, float(transport.get("public_transit_km", 0.0))),
            "flight_km": max(0.0, float(transport.get("flight_km", 0.0)))
        }
        cleaned_energy = {
            "grid_kwh": max(0.0, float(energy.get("grid_kwh", 0.0))),
            "clean_kwh": max(0.0, float(energy.get("clean_kwh", 0.0)))
        }
    except (ValueError, TypeError):
        return False, "Calculator numeric parameters must be valid positive numbers", {}

    # Strict range boundary protection (Security / Overflow Defense)
    for k, val in cleaned_transport.items():
        if val > 100000.0:
            return False, f"Transit parameter '{k}' exceeds the maximum allowed logging limit (100,000 km/mo)", {}
            
    for k, val in cleaned_energy.items():
        if val > 50000.0:
            return False, f"Energy parameter '{k}' exceeds the maximum allowed logging limit (50,000 kWh/mo)", {}

    return True, None, {
        "transport": cleaned_transport,
        "energy": cleaned_energy,
        "food": {"diet": diet},
        "consumption": {"shopping_habit": shopping}
    }

def validate_simulation(data: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validates interactive scenario changes for the simulator.
    """
    if not data:
        return False, "Simulation options cannot be empty", {}

    try:
        # Example changes: public transit shift %, meat reduction %, green energy transition %
        public_transit_shift = max(0.0, min(100.0, float(data.get("public_transit_shift", 0.0))))
        meat_reduction = max(0.0, min(100.0, float(data.get("meat_reduction", 0.0))))
        clean_energy_shift = max(0.0, min(100.0, float(data.get("clean_energy_shift", 0.0))))
        
        # Base calculator structure to compare against
        is_base_valid, base_err, base_cleaned = validate_carbon_input(data.get("base_footprint"))
        if not is_base_valid:
            return False, f"Invalid baseline footprint reference: {base_err}", {}

    except (ValueError, TypeError) as e:
        return False, f"Invalid numeric parameters in simulator constraints: {str(e)}", {}

    return True, None, {
        "public_transit_shift": public_transit_shift,
        "meat_reduction": meat_reduction,
        "clean_energy_shift": clean_energy_shift,
        "base_footprint": base_cleaned
    }

def validate_analytics_event(data: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validates telemetry events fired from the client.
    """
    if not data:
        return False, "Analytics payload cannot be empty", {}

    event_type = clean_string(data.get("event_type", ""))
    metadata = data.get("metadata", {})

    if not event_type:
        return False, "Event type is a required parameter", {}
    
    if not isinstance(metadata, dict):
        return False, "Telemetry metadata must be an object", {}

    # Standardize event kinds
    allowed_events = ["calculator_submitted", "goal_completed", "simulation_run", "ai_recommendation_accepted"]
    if event_type not in allowed_events:
        return False, f"Event type must be one of {allowed_events}", {}

    return True, None, {
        "event_type": event_type,
        "metadata": metadata
    }
