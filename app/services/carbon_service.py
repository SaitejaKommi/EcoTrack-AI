"""
Carbon Service Module for CarbonWise AI.
Responsible for calculating carbon footprints, calculating Eco Scores,
storing calculator history, running simulation scenarios, and evaluation of badges.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from app.db import get_db
from app.constants import EMISSION_FACTORS, SCORE_WEIGHTS, CATEGORY_BASELINES
from app.services.user_service import UserService

class CarbonService:
    """Service class for carbon calculators, history, simulator projections, and Eco Score math."""

    @staticmethod
    def calculate_category_emissions(data: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculates carbon emissions in kg CO2e per month for each category.
        """
        # 1. Transport calculations
        t = data.get("transport", {})
        gas_car = t.get("gas_car_km", 0.0) * EMISSION_FACTORS["transport"]["gas_car"]
        electric_car = t.get("electric_car_km", 0.0) * EMISSION_FACTORS["transport"]["electric_car"]
        transit = t.get("public_transit_km", 0.0) * EMISSION_FACTORS["transport"]["public_transit"]
        flights = t.get("flight_km", 0.0) * EMISSION_FACTORS["transport"]["flight"]
        transport_total = gas_car + electric_car + transit + flights

        # 2. Energy calculations
        e = data.get("energy", {})
        grid_electricity = e.get("grid_kwh", 0.0) * EMISSION_FACTORS["energy"]["grid_electricity"]
        clean_energy = e.get("clean_kwh", 0.0) * EMISSION_FACTORS["energy"]["clean_energy"]
        energy_total = grid_electricity + clean_energy

        # 3. Food calculations (diet scale per month based on 90 meals)
        f = data.get("food", {})
        diet_type = f.get("diet", "balanced")
        food_total = EMISSION_FACTORS["food"].get(diet_type, 1.5) * 90.0

        # 4. Consumption calculations
        c = data.get("consumption", {})
        shopping_habit = c.get("shopping_habit", "average_shopper")
        consumption_total = EMISSION_FACTORS["consumption"].get(shopping_habit, 75.0)

        return {
            "transport": round(transport_total, 2),
            "energy": round(energy_total, 2),
            "food": round(food_total, 2),
            "consumption": round(consumption_total, 2),
            "total": round(transport_total + energy_total + food_total + consumption_total, 2)
        }

    @staticmethod
    def calculate_eco_score(emissions: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
        """
        Calculates category scores and the overall 0-100 Eco Score.
        A score of 50 indicates emissions matching the national average baseline.
        Lower emissions yield a score closer to 100, while higher emissions drop toward 0.
        """
        category_scores: Dict[str, float] = {}
        total_score = 0.0

        for category, baseline in CATEGORY_BASELINES.items():
            user_emissions = emissions.get(category, 0.0)
            # Math: 100 - (user_emissions / baseline) * 50
            score = 100.0 - (user_emissions / baseline) * 50.0
            score = max(0.0, min(100.0, score))
            category_scores[category] = round(score, 2)
            
            # Apply weights
            total_score += score * SCORE_WEIGHTS.get(category, 0.25)

        return round(total_score, 2), category_scores

    @staticmethod
    def check_and_award_carbon_badges(user_id: str, input_data: Dict[str, Any], eco_score: float) -> List[str]:
        """
        Evaluates user carbon footprint input data against badge conditions.
        Returns a list of badge_ids newly unlocked during this check.
        """
        awarded_badges = []

        # 1. Check Transit Hero
        t = input_data.get("transport", {})
        gas_car = t.get("gas_car_km", 0.0)
        electric_car = t.get("electric_car_km", 0.0)
        transit = t.get("public_transit_km", 0.0)
        total_land_travel = gas_car + electric_car + transit
        if total_land_travel > 0:
            clean_share = (electric_car + transit) / total_land_travel
            if clean_share >= 0.8:
                if UserService.award_badge(user_id, "transit_hero"):
                    awarded_badges.append("transit_hero")

        # 2. Check Green Diet
        f = input_data.get("food", {})
        diet = f.get("diet", "balanced")
        if diet in ["vegetarian", "vegan"]:
            if UserService.award_badge(user_id, "green_diet"):
                awarded_badges.append("green_diet")

        # 3. Check Energy Wizard
        e = input_data.get("energy", {})
        grid = e.get("grid_kwh", 0.0)
        clean = e.get("clean_kwh", 0.0)
        total_energy = grid + clean
        if total_energy > 0:
            clean_share = clean / total_energy
            if clean_share >= 0.8:
                if UserService.award_badge(user_id, "energy_wizard"):
                    awarded_badges.append("energy_wizard")

        # 4. Check Eco Warrior
        if eco_score >= 85.0:
            if UserService.award_badge(user_id, "eco_warrior"):
                awarded_badges.append("eco_warrior")

        return awarded_badges

    @staticmethod
    def save_calculation(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates emissions and score, saves to DB history, and evaluates badges.
        """
        emissions = CarbonService.calculate_category_emissions(data)
        eco_score, category_scores = CarbonService.calculate_eco_score(emissions)
        
        # Award streaks and update active record
        UserService.update_activity_streak(user_id)
        newly_awarded_badges = CarbonService.check_and_award_carbon_badges(user_id, data, eco_score)
        
        db = get_db()
        entry = {
            "user_id": user_id,
            "inputs": data,
            "emissions": emissions,
            "eco_score": eco_score,
            "category_scores": category_scores,
            "created_at": datetime.utcnow().isoformat()
        }
        
        db["calculations"].insert_one(entry)
        
        # Serialize _id for JSON transfers
        if "_id" in entry:
            entry["id"] = str(entry["_id"])
            del entry["_id"]
            
        entry["newly_awarded_badges"] = newly_awarded_badges
        return entry

    @staticmethod
    def get_user_history(user_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Retrieves user historical footprint entries ordered by date (newest first).
        """
        db = get_db()
        cursor = db["calculations"].find({"user_id": user_id})
        # Sort by creation date
        cursor.sort("created_at", -1)
        cursor.limit(limit)
        
        history = []
        for entry in cursor:
            if "_id" in entry:
                entry["id"] = str(entry["_id"])
                del entry["_id"]
            history.append(entry)
        return history

    @staticmethod
    def simulate_reduction(sim_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs scenarios against base footprint calculations.
        Parameters:
            sim_params: contains public_transit_shift (%), meat_reduction (%),
            clean_energy_shift (%), and base_footprint (Dict).
        """
        base = sim_params["base_footprint"]
        transit_shift = sim_params["public_transit_shift"] / 100.0
        meat_red = sim_params["meat_reduction"] / 100.0
        energy_shift = sim_params["clean_energy_shift"] / 100.0

        # Create simulated clone of inputs
        sim_inputs = {
            "transport": base["transport"].copy(),
            "energy": base["energy"].copy(),
            "food": base["food"].copy(),
            "consumption": base["consumption"].copy()
        }

        # 1. Public Transit shift: Converts a percentage of gasoline car kilometers to public transit.
        gas_car = base["transport"]["gas_car_km"]
        shifted_km = gas_car * transit_shift
        sim_inputs["transport"]["gas_car_km"] = max(0.0, gas_car - shifted_km)
        sim_inputs["transport"]["public_transit_km"] += shifted_km

        # 2. Clean energy shift: Converts percentage of grid power to clean energy.
        grid_kwh = base["energy"]["grid_kwh"]
        shifted_kwh = grid_kwh * energy_shift
        sim_inputs["energy"]["grid_kwh"] = max(0.0, grid_kwh - shifted_kwh)
        sim_inputs["energy"]["clean_kwh"] += shifted_kwh

        # 3. Meat reduction: Scales diet emissions from beef/balanced towards vegan/vegetarian.
        diet = base["food"]["diet"]
        # Standard meals per month = 90
        # If diet is meat_heavy, reducing meat shifts meals to vegan/vegetarian. We calculate simulated emissions directly.
        # To make it simple, we compute the base emissions and scale them.
        base_emissions = CarbonService.calculate_category_emissions(base)
        sim_emissions = CarbonService.calculate_category_emissions(sim_inputs)
        
        # Apply dietary transition math directly to food emissions
        food_base = sim_emissions["food"]
        # Shifting diet: Veg/Vegan factor averages ~ 0.6. Meat average diet is 1.5, heavy is 3.0.
        # Reduction shifts food carbon down towards vegan level (0.4 * 90 = 36.0 kg)
        target_food_min = EMISSION_FACTORS["food"]["vegan"] * 90.0
        potential_diet_savings = max(0.0, food_base - target_food_min)
        sim_emissions["food"] = round(food_base - (potential_diet_savings * meat_red), 2)

        # Recalculate totals
        sim_emissions["total"] = round(
            sim_emissions["transport"] + sim_emissions["energy"] + sim_emissions["food"] + sim_emissions["consumption"],
            2
        )

        base_score, _ = CarbonService.calculate_eco_score(base_emissions)
        sim_score, sim_cat_scores = CarbonService.calculate_eco_score(sim_emissions)

        reduction_absolute = round(max(0.0, base_emissions["total"] - sim_emissions["total"]), 2)
        reduction_percentage = round((reduction_absolute / base_emissions["total"] * 100.0), 2) if base_emissions["total"] > 0 else 0.0

        return {
            "current_emissions": base_emissions,
            "projected_emissions": sim_emissions,
            "current_score": base_score,
            "projected_score": sim_score,
            "projected_category_scores": sim_cat_scores,
            "potential_reduction_kg": reduction_absolute,
            "potential_reduction_pct": reduction_percentage
        }
