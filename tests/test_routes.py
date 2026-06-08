"""
Integration Tests for Blueprint Routes in CarbonWise AI.
Validates route guards, validation schema boundaries, and JSON format returns.
"""

import json
import pytest

HEADERS = {"X-Requested-With": "XMLHttpRequest"}

def test_csrf_protection_blocks_anonymous_post(client):
    """Verifies that stateful POST endpoints require the X-Requested-With CSRF header."""
    signup_payload = {
        "username": "tester1",
        "email": "test1@carbonwise.com",
        "password": "securepassword"
    }
    # Send post request without CSRF header
    res = client.post('/api/auth/register', json=signup_payload)
    assert res.status_code == 400
    res_data = json.loads(res.data)
    assert "CSRF" in res_data["message"]

def test_auth_endpoints(client):
    """Tests registration, login, profile authentication guards, and logouts."""
    
    # 1. Access profile without credentials
    res = client.get('/api/auth/profile')
    assert res.status_code == 401
    
    # 2. Register user profile
    signup_payload = {
        "username": "tester1",
        "email": "test1@carbonwise.com",
        "password": "securepassword"
    }
    res = client.post('/api/auth/register', json=signup_payload, headers=HEADERS)
    assert res.status_code == 201
    
    # 3. Log in
    login_payload = {
        "email": "test1@carbonwise.com",
        "password": "securepassword"
    }
    res = client.post('/api/auth/login', json=login_payload, headers=HEADERS)
    assert res.status_code == 200
    res_data = json.loads(res.data)
    assert res_data["status"] == "success"
    
    # 4. Check active profile (Session cookies are held automatically by the client)
    res = client.get('/api/auth/profile')
    assert res.status_code == 200
    profile_data = json.loads(res.data)["data"]
    assert profile_data["username"] == "tester1"
    
    # 5. Log out
    res = client.post('/api/auth/logout', headers=HEADERS)
    assert res.status_code == 200
    
    # 6. Check profile again
    res = client.get('/api/auth/profile')
    assert res.status_code == 401

def test_carbon_and_coach_protected_endpoints(client):
    """Verifies that carbon calculator and coaching API routes block anonymous users."""
    assert client.post('/api/carbon/calculate', json={}, headers=HEADERS).status_code == 401
    assert client.get('/api/carbon/history').status_code == 401
    assert client.post('/api/carbon/simulate', json={}, headers=HEADERS).status_code == 401
    assert client.get('/api/carbon/predict').status_code == 401
    assert client.get('/api/coach/insights').status_code == 401
    assert client.get('/api/coach/plan').status_code == 401
    assert client.post('/api/coach/goals/complete', json={}, headers=HEADERS).status_code == 401
    assert client.post('/api/analytics/event', json={}, headers=HEADERS).status_code == 401
    assert client.get('/api/analytics/summary').status_code == 401

def test_authenticated_carbon_workflow(auth_client):
    """Tests calculator submits, historical trend queries, predictions, and simulations."""
    
    # 1. Run calculator
    calc_payload = {
        "transport": {
            "gas_car_km": 150.0,
            "electric_car_km": 50.0,
            "public_transit_km": 200.0,
            "flight_km": 0.0
        },
        "energy": {
            "grid_kwh": 300.0,
            "clean_kwh": 50.0
        },
        "food": {
            "diet": "balanced"
        },
        "consumption": {
            "shopping_habit": "average_shopper"
        }
    }
    res = auth_client.post('/api/carbon/calculate', json=calc_payload, headers=HEADERS)
    assert res.status_code == 200
    calc_res = json.loads(res.data)["data"]
    assert "emissions" in calc_res
    assert "eco_score" in calc_res
    
    # 2. Get history log
    res = auth_client.get('/api/carbon/history')
    assert res.status_code == 200
    history = json.loads(res.data)["data"]
    assert len(history) >= 1
    
    # 3. Simulate scenario shifts
    sim_payload = {
        "public_transit_shift": 40.0,
        "meat_reduction": 50.0,
        "clean_energy_shift": 90.0,
        "base_footprint": calc_payload
    }
    res = auth_client.post('/api/carbon/simulate', json=sim_payload, headers=HEADERS)
    assert res.status_code == 200
    sim_res = json.loads(res.data)["data"]
    assert "potential_reduction_kg" in sim_res
    
    # 4. Get future prediction trends
    res = auth_client.get('/api/carbon/predict')
    assert res.status_code == 200
    pred_res = json.loads(res.data)["data"]
    assert "projection_30_days" in pred_res

def test_authenticated_coaching_workflow(auth_client):
    """Tests receiving insights, action plans, and completing goals."""
    
    # Set up footprint baseline entry first
    calc_payload = {
        "transport": {"gas_car_km": 10.0, "electric_car_km": 0.0, "public_transit_km": 0.0, "flight_km": 0.0},
        "energy": {"grid_kwh": 10.0, "clean_kwh": 0.0},
        "food": {"diet": "vegetarian"},
        "consumption": {"shopping_habit": "minimalist"}
    }
    auth_client.post('/api/carbon/calculate', json=calc_payload, headers=HEADERS)
    
    # 1. Fetch coach insights
    res = auth_client.get('/api/coach/insights')
    assert res.status_code == 200
    insights = json.loads(res.data)["data"]
    assert "insights" in insights
    assert "weekly_goals" in insights
    
    # 2. Get prioritized action checklists
    res = auth_client.get('/api/coach/plan')
    assert res.status_code == 200
    plan = json.loads(res.data)["data"]
    assert "daily" in plan
    
    # 3. Complete a goal
    goal_payload = {
        "goal_title": "Clean Energy Switch",
        "carbon_saved_kg": 12.5
    }
    res = auth_client.post('/api/coach/goals/complete', json=goal_payload, headers=HEADERS)
    assert res.status_code == 200
    summary = json.loads(res.data)["data"]
    assert summary["goals_completed"] == 1
    assert summary["estimated_carbon_saved_kg"] == 12.5

def test_analytics_endpoints(auth_client):
    """Tests manual analytics event posts and summary checks."""
    event_payload = {
        "event_type": "simulation_run",
        "metadata": {"custom_param": "sim_testing"}
    }
    res = auth_client.post('/api/analytics/event', json=event_payload, headers=HEADERS)
    assert res.status_code == 200
    
    res = auth_client.get('/api/analytics/summary')
    assert res.status_code == 200
    summary_data = json.loads(res.data)["data"]
    assert "simulations_run" in summary_data

def test_error_handlers(client):
    """Tests that default Flask status errors route to standard JSON payloads."""
    # Test 404 handler
    res = client.get('/api/non_existent_route')
    assert res.status_code == 404
    res_data = json.loads(res.data)
    assert res_data["status"] == "error"
    assert "Not Found" in res_data["message"]
    
    # Test 400 Bad Request error handler
    # Posting an invalid content-type or empty POST triggers 400
    res = client.post('/api/auth/register', data="invalid_json", headers=HEADERS)
    assert res.status_code == 400
    res_data = json.loads(res.data)
    assert res_data["status"] == "error"

    # Test 401 error handler
    res = client.get('/test-error/401')
    assert res.status_code == 401
    assert "Unauthorized" in json.loads(res.data)["message"]

    # Test 403 error handler
    res = client.get('/test-error/403')
    assert res.status_code == 403
    assert "Forbidden" in json.loads(res.data)["message"]

    # Test 429 error handler
    res = client.get('/test-error/429')
    assert res.status_code == 429
    assert "Too Many Requests" in json.loads(res.data)["message"]

    # Test 500 error handler
    res = client.get('/test-error/500')
    assert res.status_code == 500
    assert "Internal Server Error" in json.loads(res.data)["message"]

def test_endpoints_fail_without_history(client):
    """Tests that coaching, planning, and predicting endpoints return 400 when no history exists."""
    headers = {"X-Requested-With": "XMLHttpRequest"}
    signup = {"username": "nohistory", "email": "nohistory@test.com", "password": "password"}
    client.post('/api/auth/register', json=signup, headers=headers)
    
    login = {"email": "nohistory@test.com", "password": "password"}
    client.post('/api/auth/login', json=login, headers=headers)
    
    # Check insights
    res = client.get('/api/coach/insights')
    assert res.status_code == 400
    assert "carbon calculation first" in json.loads(res.data)["message"]

    # Check plan
    res = client.get('/api/coach/plan')
    assert res.status_code == 400
    
    # Check predict
    res = client.get('/api/carbon/predict')
    assert res.status_code == 400

