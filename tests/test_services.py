"""
Unit Tests for Service Layer in CarbonWise AI.
Validates math algorithms, streak progression, badge locks, and telemetry log functions.
"""

import pytest
from app.services.user_service import UserService
from app.services.carbon_service import CarbonService
from app.services.analytics_service import AnalyticsService
from app.services.gemini_service import GeminiService
from app.constants import BADGE_CONFIGS

def test_create_and_auth_user(db_mock):
    """Tests registration validation and session authentication checks."""
    user_data = {
        "username": "tester",
        "email": "test@carbonwise.com",
        "password": "securepassword"
    }
    
    # Register user
    success, res = UserService.create_user(user_data)
    assert success is True
    assert isinstance(res, str)
    
    # Attempt duplicate email signup
    success_dup, err_dup = UserService.create_user(user_data)
    assert success_dup is False
    assert "already exists" in err_dup
    
    # Authenticate user
    auth_data = {
        "email": "test@carbonwise.com",
        "password": "securepassword"
    }
    user_info = UserService.authenticate_user(auth_data)
    assert user_info is not None
    assert user_info["username"] == "tester"
    
    # Attempt bad password
    bad_auth = {
        "email": "test@carbonwise.com",
        "password": "wrongpassword"
    }
    assert UserService.authenticate_user(bad_auth) is None

def test_activity_streak(db_mock):
    """Verifies that daily active checks correctly scale or reset user streaks."""
    user_data = {
        "username": "streak_tester",
        "email": "streak@carbonwise.com",
        "password": "password"
    }
    _, user_id = UserService.create_user(user_data)
    
    # First update sets streak to 1
    streak1 = UserService.update_activity_streak(user_id)
    assert streak1 == 1
    
    # Same day update keeps streak at 1
    streak2 = UserService.update_activity_streak(user_id)
    assert streak2 == 1

def test_carbon_math_and_scorecard():
    """Validates emission calculation equations and Eco Score tiers."""
    inputs = {
        "transport": {
            "gas_car_km": 100.0,
            "electric_car_km": 0.0,
            "public_transit_km": 0.0,
            "flight_km": 0.0
        },
        "energy": {
            "grid_kwh": 100.0,
            "clean_kwh": 0.0
        },
        "food": {
            "diet": "balanced"
        },
        "consumption": {
            "shopping_habit": "average_shopper"
        }
    }
    
    emissions = CarbonService.calculate_category_emissions(inputs)
    # Gas Car emissions: 100 km * 0.220 = 22 kg
    assert emissions["transport"] == 22.0
    # Grid emissions: 100 kWh * 0.475 = 47.5 kg
    assert emissions["energy"] == 47.50
    # Food: balanced = 1.5 * 90 = 135 kg
    assert emissions["food"] == 135.0
    # Consumption: average = 75 kg
    assert emissions["consumption"] == 75.0
    
    total = 22.0 + 47.50 + 135.0 + 75.0
    assert emissions["total"] == total
    
    # Score calculations
    eco_score, cat_scores = CarbonService.calculate_eco_score(emissions)
    assert 0.0 <= eco_score <= 100.0
    assert "transport" in cat_scores
    assert "energy" in cat_scores

def test_badge_award_conditions(db_mock):
    """Verifies badge triggers (Transit Hero, Veg diet, Clean energy)."""
    user_data = {
        "username": "badge_tester",
        "email": "badges@carbonwise.com",
        "password": "password"
    }
    _, user_id = UserService.create_user(user_data)
    
    # Test Green Diet badge check
    inputs = {
        "transport": {"gas_car_km": 500.0, "electric_car_km": 0.0, "public_transit_km": 0.0, "flight_km": 0.0},
        "energy": {"grid_kwh": 200.0, "clean_kwh": 0.0},
        "food": {"diet": "vegan"}, # Triggers badge
        "consumption": {"shopping_habit": "average_shopper"}
    }
    
    calc_res = CarbonService.save_calculation(user_id, inputs)
    assert "green_diet" in calc_res["newly_awarded_badges"]
    
    # Re-run calculator with vegan diet; should not re-award
    calc_res_again = CarbonService.save_calculation(user_id, inputs)
    assert "green_diet" not in calc_res_again["newly_awarded_badges"]

def test_simulator_projection():
    """Validates transit shifting and energy swapping within the Simulator."""
    base_footprint = {
        "transport": {
            "gas_car_km": 1000.0,
            "electric_car_km": 0.0,
            "public_transit_km": 0.0,
            "flight_km": 0.0
        },
        "energy": {
            "grid_kwh": 500.0,
            "clean_kwh": 0.0
        },
        "food": {
            "diet": "meat_heavy"
        },
        "consumption": {
            "shopping_habit": "high_shopper"
        }
    }
    
    sim_params = {
        "public_transit_shift": 50.0, # shift 50% to transit
        "meat_reduction": 100.0,       # Veg diet shift
        "clean_energy_shift": 80.0,   # shift 80% to clean
        "base_footprint": base_footprint
    }
    
    results = CarbonService.simulate_reduction(sim_params)
    assert results["potential_reduction_kg"] > 0.0
    assert results["projected_emissions"]["total"] < results["current_emissions"]["total"]
    assert results["projected_score"] > results["current_score"]

def test_telemetry_logging(db_mock):
    """Verifies that interaction clicks and savings are logged in telemetry collections."""
    user_id = "analyt_123"
    AnalyticsService.log_event(user_id, "calculator_submitted", {"score": 75.0})
    AnalyticsService.log_event(user_id, "goal_completed", {"carbon_saved_kg": 15.5})
    AnalyticsService.log_event(user_id, "goal_completed", {"carbon_saved_kg": 4.5})
    
    summary = AnalyticsService.get_user_analytics_summary(user_id)
    assert summary["calculations_run"] == 1
    assert summary["goals_completed"] == 2
    assert summary["estimated_carbon_saved_kg"] == 20.0

def test_gemini_fallback_offline():
    """Verifies that the Gemini API wrapper runs locally in fallback mode when keys are blank and caching works."""
    # Reset caches
    GeminiService._insights_cache.clear()
    GeminiService._action_plan_cache.clear()

    # Test insights
    footprint = {
        "emissions": {"transport": 100.0, "energy": 120.0, "food": 90.0, "consumption": 30.0, "total": 340.0},
        "category_scores": {"transport": 60, "energy": 55, "food": 70, "consumption": 80},
        "eco_score": 64.0,
        "inputs": {
            "food": {"diet": "balanced"},
            "consumption": {"shopping_habit": "average_shopper"}
        }
    }
    
    # Call 1 (Cache Miss)
    insights1 = GeminiService.generate_coaching_insights("usr_id", footprint)
    assert "insights" in insights1
    assert len(insights1["insights"]) == 3
    assert "weekly_goals" in insights1
    assert len(GeminiService._insights_cache) == 1

    # Call 2 (Cache Hit)
    insights2 = GeminiService.generate_coaching_insights("usr_id", footprint)
    assert insights1 == insights2

    # Test Action Plan caching
    # Call 1 (Cache Miss)
    plan1 = GeminiService.generate_action_plan("usr_id", footprint)
    assert "daily" in plan1
    assert len(GeminiService._action_plan_cache) == 1

    # Call 2 (Cache Hit)
    plan2 = GeminiService.generate_action_plan("usr_id", footprint)
    assert plan1 == plan2
    
    # Test projection
    proj = GeminiService.predict_future_footprint([footprint])
    assert proj["projection_30_days"] > 0
    assert "reasoning" in proj

def test_user_service_invalid_error_paths(db_mock):
    """Tests that user service returns fallback values when querying non-existent users or badges."""
    # Streak update on invalid user
    streak = UserService.update_activity_streak("invalid_user_id_999")
    assert streak == 0
    
    # Badge award on invalid user
    res = UserService.award_badge("invalid_user_id_999", "transit_hero")
    assert res is False
    
    # Badge award for invalid badge ID
    user_data = {"username": "tester", "email": "tester@test.com", "password": "password"}
    _, user_id = UserService.create_user(user_data)
    res = UserService.award_badge(user_id, "invalid_badge_id_999")
    assert res is False

