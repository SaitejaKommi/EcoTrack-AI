"""
Carbon Footprint Service for CarbonWise AI.

Provides the core business logic for calculating carbon emissions, computing
Eco Scores, persisting calculator history, running lifestyle scenario
simulations, and evaluating gamification badge eligibility.

Emission calculations apply scientifically-based factors sourced from the
EPA and IPCC 2023 methodology guidelines, centralised in ``app.constants``.
The Eco Score is a proprietary 0–100 metric where 50 represents the national
average baseline; higher scores indicate a smaller-than-average footprint.

Architecture role: Business logic / service layer — mediates between the
route controller layer and the database. Must not import from route modules
or depend on Flask's request context.

Typical usage:
    from app.services.carbon_service import CarbonService
    emissions = CarbonService.calculate_category_emissions(validated_inputs)
    eco_score, category_scores = CarbonService.calculate_eco_score(emissions)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.constants import (
    CATEGORY_BASELINES,
    CLEAN_ENERGY_BADGE_THRESHOLD,
    CLEAN_TRAVEL_BADGE_THRESHOLD,
    DEFAULT_AVERAGE_SHOPPER_EMISSIONS,
    DEFAULT_MEAT_DIET_EMISSIONS,
    ECO_WARRIOR_BADGE_THRESHOLD,
    EMISSION_FACTORS,
    MEALS_PER_MONTH,
    SCORE_SCALING_MULTIPLIER,
    SCORE_SCALING_OFFSET,
    SCORE_WEIGHTS,
)
from app.db import get_db
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


class CarbonService:
    """Service class for carbon calculations, history, simulation, and badge evaluation.

    All methods are ``@staticmethod`` — no instance state is held. Callers
    interact with the database through ``get_db()`` which provides either a
    live MongoDB handle or the JSONDatabaseMock depending on configuration.
    """

    @staticmethod
    def calculate_category_emissions(data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate monthly carbon emissions in kg CO2e for each lifestyle category.

        Applies IPCC/EPA emission factors from ``EMISSION_FACTORS`` to the
        user's activity inputs across four categories: transport, energy,
        food, and consumption. Unrecognised diet or shopping types fall back
        to balanced/average defaults to prevent calculation failures.

        Args:
            data: Validated calculator inputs containing nested dicts for
                ``"transport"``, ``"energy"``, ``"food"``, and ``"consumption"``.

        Returns:
            Dict[str, float]: Emission totals per category and an overall
            ``"total"`` key. All values are rounded to two decimal places.
            Keys: ``"transport"``, ``"energy"``, ``"food"``, ``"consumption"``,
            ``"total"``.
        """
        transport_total = _calc_transport_emissions(data.get("transport", {}))
        energy_total = _calc_energy_emissions(data.get("energy", {}))
        food_total = _calc_food_emissions(data.get("food", {}))
        consumption_total = _calc_consumption_emissions(data.get("consumption", {}))

        return {
            "transport": round(transport_total, 2),
            "energy": round(energy_total, 2),
            "food": round(food_total, 2),
            "consumption": round(consumption_total, 2),
            "total": round(transport_total + energy_total + food_total + consumption_total, 2),
        }

    @staticmethod
    def calculate_eco_score(
        emissions: Dict[str, float]
    ) -> Tuple[float, Dict[str, float]]:
        """Compute the overall Eco Score and per-category scores from emission values.

        The scoring algorithm maps each category's emissions to a 0–100 scale
        relative to the national average baseline stored in ``CATEGORY_BASELINES``.
        A score of 50 means the user matches the baseline exactly; scores above
        50 indicate below-average emissions (greener lifestyle), and below 50
        indicates above-average emissions.

        Formula per category:
            score = SCORE_SCALING_OFFSET – (user_emissions / baseline) * SCORE_SCALING_MULTIPLIER
        The overall score is the weighted average across all four categories
        using the weights defined in ``SCORE_WEIGHTS``.

        Args:
            emissions: Category emission values in kg CO2e as returned by
                ``calculate_category_emissions()``.

        Returns:
            Tuple[float, Dict[str, float]]:
                - Overall eco score clamped to [0, 100], rounded to 2 d.p.
                - Per-category score dict with keys ``"transport"``, ``"energy"``,
                  ``"food"``, ``"consumption"``.

        Raises:
            No exceptions — missing emission keys default to 0.0.
        """
        category_scores: Dict[str, float] = {}
        total_score = 0.0

        for category, baseline in CATEGORY_BASELINES.items():
            user_emissions = emissions.get(category, 0.0)
            # Linear interpolation: user at baseline → score 50; zero emissions → score 100
            raw_score = SCORE_SCALING_OFFSET - (user_emissions / baseline) * SCORE_SCALING_MULTIPLIER
            # Clamp to valid [0, SCORE_SCALING_OFFSET] range
            score = max(0.0, min(SCORE_SCALING_OFFSET, raw_score))
            category_scores[category] = round(score, 2)
            # Accumulate weighted contribution to the overall score
            total_score += score * SCORE_WEIGHTS.get(category, 0.25)

        return round(total_score, 2), category_scores

    @staticmethod
    def check_and_award_carbon_badges(
        user_id: str,
        input_data: Dict[str, Any],
        eco_score: float,
    ) -> List[str]:
        """Evaluate badge eligibility conditions and award newly unlocked badges.

        Checks four badge types against the current calculator submission:
        - **Transit Hero**: ≥80% of land travel via EV or public transit.
        - **Green Diet**: Vegetarian or vegan diet selected.
        - **Energy Wizard**: ≥80% of total energy from clean/solar sources.
        - **Eco Warrior**: Overall eco score ≥ 85.

        Args:
            user_id: Authenticated user identifier used to look up existing badges.
            input_data: Validated calculator inputs (same structure as ``calculate_category_emissions`` input).
            eco_score: Computed overall eco score for this submission.

        Returns:
            List[str]: Badge IDs newly awarded during this check. Already-held
            badges are silently skipped. Returns ``[]`` when no new badges qualify.

        Raises:
            No exceptions — badge award failures are handled inside UserService.
        """
        awarded_badges: List[str] = []

        awarded_badges.extend(_check_transit_hero_badge(user_id, input_data))
        awarded_badges.extend(_check_green_diet_badge(user_id, input_data))
        awarded_badges.extend(_check_energy_wizard_badge(user_id, input_data))
        awarded_badges.extend(_check_eco_warrior_badge(user_id, eco_score))

        return awarded_badges

    @staticmethod
    def save_calculation(
        user_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate, persist, and return a complete footprint entry for the user.

        Orchestrates the full calculation pipeline: emission calculation → eco
        score computation → streak update → badge evaluation → database persist.
        The returned document includes all calculation details plus any newly
        unlocked badge IDs so the frontend can display achievement alerts.

        Args:
            user_id: Authenticated user identifier.
            data: Validated calculator inputs from ``validate_carbon_input()``.

        Returns:
            Dict[str, Any]: Persisted calculation document containing
            ``"inputs"``, ``"emissions"``, ``"eco_score"``, ``"category_scores"``,
            ``"created_at"``, ``"id"``, and ``"newly_awarded_badges"``.

        Raises:
            No exceptions — database errors propagate as-is to the route handler.
        """
        emissions = CarbonService.calculate_category_emissions(data)
        eco_score, category_scores = CarbonService.calculate_eco_score(emissions)

        # Update the user's consecutive-day streak before badge evaluation
        UserService.update_activity_streak(user_id)
        newly_awarded_badges = CarbonService.check_and_award_carbon_badges(
            user_id, data, eco_score
        )

        db = get_db()
        entry: Dict[str, Any] = {
            "user_id": user_id,
            "inputs": data,
            "emissions": emissions,
            "eco_score": eco_score,
            "category_scores": category_scores,
            "created_at": datetime.utcnow().isoformat(),
        }
        db["calculations"].insert_one(entry)

        # Serialise the internal _id field to a JSON-safe string
        if "_id" in entry:
            entry["id"] = str(entry["_id"])
            del entry["_id"]

        entry["newly_awarded_badges"] = newly_awarded_badges
        return entry

    @staticmethod
    def get_user_history(
        user_id: str,
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        """Retrieve historical footprint entries for a user, newest first.

        Args:
            user_id: Authenticated user identifier.
            limit: Maximum number of records to return. Defaults to ``12``
                (one year of monthly entries).

        Returns:
            List[Dict[str, Any]]: Calculation documents sorted by
            ``"created_at"`` descending. Each document has a JSON-safe
            string ``"id"`` field replacing the database ``_id``.
        """
        db = get_db()
        cursor = db["calculations"].find({"user_id": user_id})
        # Sort newest-first so the most recent calculation is always index 0
        cursor.sort("created_at", -1)
        cursor.limit(limit)

        history: List[Dict[str, Any]] = []
        for entry in cursor:
            if "_id" in entry:
                entry["id"] = str(entry["_id"])
                del entry["_id"]
            history.append(entry)
        return history

    @staticmethod
    def simulate_reduction(sim_params: Dict[str, Any]) -> Dict[str, Any]:
        """Project the emission impact of lifestyle habit changes.

        Accepts percentage shift parameters for three levers — public transit
        adoption, meat diet reduction, and clean energy transition — and
        calculates the resulting emission levels and score improvement compared
        to the user's current baseline footprint.

        Args:
            sim_params: Simulation parameters containing:
                - ``"public_transit_shift"``: Percentage of gas-car km to shift
                  to public transit (0–100).
                - ``"meat_reduction"``: Percentage dietary carbon reduction
                  towards vegan levels (0–100).
                - ``"clean_energy_shift"``: Percentage of grid kWh to shift
                  to clean energy sources (0–100).
                - ``"base_footprint"``: Validated base calculator inputs.

        Returns:
            Dict[str, Any]: Comparison result containing:
                - ``"current_emissions"``: Base emission totals.
                - ``"projected_emissions"``: Simulated emission totals.
                - ``"current_score"``: Base eco score.
                - ``"projected_score"``: Simulated eco score.
                - ``"projected_category_scores"``: Per-category scores after simulation.
                - ``"potential_reduction_kg"``: Absolute kg CO2e saved.
                - ``"potential_reduction_pct"``: Percentage reduction relative to baseline.

        Raises:
            No exceptions — the base footprint is assumed already validated.
        """
        base = sim_params["base_footprint"]
        # Convert percentage shifts to decimal multipliers for arithmetic
        transit_shift_ratio = sim_params["public_transit_shift"] / 100.0
        meat_reduction_ratio = sim_params["meat_reduction"] / 100.0
        energy_shift_ratio = sim_params["clean_energy_shift"] / 100.0

        sim_inputs = _build_simulated_inputs(base, transit_shift_ratio, energy_shift_ratio)
        base_emissions = CarbonService.calculate_category_emissions(base)
        sim_emissions = CarbonService.calculate_category_emissions(sim_inputs)

        # Compute the dietary reduction separately because diet is categorical
        # (not a continuous numeric input), so we interpolate the food emission
        # value directly between its current level and the minimum (vegan) level.
        sim_emissions = _apply_dietary_reduction(
            sim_emissions, meat_reduction_ratio
        )

        base_score, _ = CarbonService.calculate_eco_score(base_emissions)
        sim_score, sim_cat_scores = CarbonService.calculate_eco_score(sim_emissions)

        reduction_absolute = round(max(0.0, base_emissions["total"] - sim_emissions["total"]), 2)
        reduction_percentage = (
            round((reduction_absolute / base_emissions["total"]) * 100.0, 2)
            if base_emissions["total"] > 0
            else 0.0
        )

        return {
            "current_emissions": base_emissions,
            "projected_emissions": sim_emissions,
            "current_score": base_score,
            "projected_score": sim_score,
            "projected_category_scores": sim_cat_scores,
            "potential_reduction_kg": reduction_absolute,
            "potential_reduction_pct": reduction_percentage,
        }


# ─── Private Helper Functions ─────────────────────────────────────────────────


def _calc_transport_emissions(transport: Dict[str, Any]) -> float:
    """Sum monthly CO2e emissions across all transport modes.

    Applies IPCC transport emission factors: gas cars emit 0.220 kg/km,
    EVs emit 0.050 kg/km (grid average), public transit 0.040 kg/km, and
    flights 0.180 kg/km per IPCC AR6 Transport chapter.

    Args:
        transport: Transport sub-dict from validated calculator inputs.

    Returns:
        float: Total transport emissions in kg CO2e for the month.
    """
    t = transport
    gas_car = t.get("gas_car_km", 0.0) * EMISSION_FACTORS["transport"]["gas_car"]
    electric_car = t.get("electric_car_km", 0.0) * EMISSION_FACTORS["transport"]["electric_car"]
    transit = t.get("public_transit_km", 0.0) * EMISSION_FACTORS["transport"]["public_transit"]
    flights = t.get("flight_km", 0.0) * EMISSION_FACTORS["transport"]["flight"]
    return gas_car + electric_car + transit + flights


def _calc_energy_emissions(energy: Dict[str, Any]) -> float:
    """Sum monthly CO2e emissions from household electricity sources.

    Grid electricity is assumed at 0.475 kg/kWh (average national intensity),
    while clean/solar energy lifecycle emissions are negligible at 0.020 kg/kWh.

    Args:
        energy: Energy sub-dict from validated calculator inputs.

    Returns:
        float: Total energy emissions in kg CO2e for the month.
    """
    e = energy
    grid = e.get("grid_kwh", 0.0) * EMISSION_FACTORS["energy"]["grid_electricity"]
    clean = e.get("clean_kwh", 0.0) * EMISSION_FACTORS["energy"]["clean_energy"]
    return grid + clean


def _calc_food_emissions(food: Dict[str, Any]) -> float:
    """Calculate monthly CO2e from the user's dietary pattern.

    Multiplies the per-meal emission factor for the selected diet type by the
    standard monthly meal count (MEALS_PER_MONTH = 90). Falls back to the
    balanced diet factor when an unrecognised diet key is encountered.

    Args:
        food: Food sub-dict from validated calculator inputs.

    Returns:
        float: Total food emissions in kg CO2e for the month.
    """
    diet_type = food.get("diet", "balanced")
    # Fallback to DEFAULT_MEAT_DIET_EMISSIONS (balanced diet) for unknown diet types
    per_meal_factor = EMISSION_FACTORS["food"].get(diet_type, DEFAULT_MEAT_DIET_EMISSIONS)
    return per_meal_factor * MEALS_PER_MONTH


def _calc_consumption_emissions(consumption: Dict[str, Any]) -> float:
    """Return monthly CO2e from discretionary shopping and consumption habits.

    Consumption emissions are expressed as a fixed monthly total rather than a
    rate, as shopping habits are categorical rather than continuous inputs.
    Unrecognised shopping habits fall back to the average_shopper level.

    Args:
        consumption: Consumption sub-dict from validated calculator inputs.

    Returns:
        float: Total consumption emissions in kg CO2e for the month.
    """
    shopping_habit = consumption.get("shopping_habit", "average_shopper")
    return EMISSION_FACTORS["consumption"].get(shopping_habit, DEFAULT_AVERAGE_SHOPPER_EMISSIONS)


def _check_transit_hero_badge(
    user_id: str,
    input_data: Dict[str, Any],
) -> List[str]:
    """Award Transit Hero badge when ≥80% of land travel uses low-emission modes.

    Calculates the ratio of (EV km + transit km) to total land travel km and
    compares it to ``CLEAN_TRAVEL_BADGE_THRESHOLD``. Only runs the check when
    the user has any recorded land travel to avoid division-by-zero.

    Args:
        user_id: Authenticated user identifier.
        input_data: Validated calculator inputs.

    Returns:
        List[str]: ``["transit_hero"]`` if newly awarded, else ``[]``.
    """
    t = input_data.get("transport", {})
    gas_car = t.get("gas_car_km", 0.0)
    electric_car = t.get("electric_car_km", 0.0)
    transit = t.get("public_transit_km", 0.0)
    total_land_travel = gas_car + electric_car + transit

    if total_land_travel > 0:
        clean_share = (electric_car + transit) / total_land_travel
        if clean_share >= CLEAN_TRAVEL_BADGE_THRESHOLD:
            if UserService.award_badge(user_id, "transit_hero"):
                return ["transit_hero"]
    return []


def _check_green_diet_badge(
    user_id: str,
    input_data: Dict[str, Any],
) -> List[str]:
    """Award Green Diet badge when the user follows a vegetarian or vegan diet.

    Args:
        user_id: Authenticated user identifier.
        input_data: Validated calculator inputs.

    Returns:
        List[str]: ``["green_diet"]`` if newly awarded, else ``[]``.
    """
    diet = input_data.get("food", {}).get("diet", "balanced")
    if diet in ["vegetarian", "vegan"]:
        if UserService.award_badge(user_id, "green_diet"):
            return ["green_diet"]
    return []


def _check_energy_wizard_badge(
    user_id: str,
    input_data: Dict[str, Any],
) -> List[str]:
    """Award Energy Wizard badge when ≥80% of energy comes from clean sources.

    Args:
        user_id: Authenticated user identifier.
        input_data: Validated calculator inputs.

    Returns:
        List[str]: ``["energy_wizard"]`` if newly awarded, else ``[]``.
    """
    e = input_data.get("energy", {})
    grid = e.get("grid_kwh", 0.0)
    clean = e.get("clean_kwh", 0.0)
    total_energy = grid + clean

    if total_energy > 0:
        clean_share = clean / total_energy
        if clean_share >= CLEAN_ENERGY_BADGE_THRESHOLD:
            if UserService.award_badge(user_id, "energy_wizard"):
                return ["energy_wizard"]
    return []


def _check_eco_warrior_badge(
    user_id: str,
    eco_score: float,
) -> List[str]:
    """Award Eco Warrior badge when the overall eco score reaches 85 or above.

    Args:
        user_id: Authenticated user identifier.
        eco_score: Computed eco score for the current submission.

    Returns:
        List[str]: ``["eco_warrior"]`` if newly awarded, else ``[]``.
    """
    if eco_score >= ECO_WARRIOR_BADGE_THRESHOLD:
        if UserService.award_badge(user_id, "eco_warrior"):
            return ["eco_warrior"]
    return []


def _build_simulated_inputs(
    base: Dict[str, Any],
    transit_shift_ratio: float,
    energy_shift_ratio: float,
) -> Dict[str, Any]:
    """Apply transit and energy shift ratios to base inputs to create simulated inputs.

    Converts a fraction of gas-car km to public transit km and a fraction of
    grid kWh to clean kWh, simulating the impact of behavioural changes.

    Args:
        base: Validated base footprint calculator inputs.
        transit_shift_ratio: Fraction [0, 1] of gas-car km to convert to transit.
        energy_shift_ratio: Fraction [0, 1] of grid kWh to convert to clean energy.

    Returns:
        Dict[str, Any]: Modified copy of ``base`` with adjusted transport and
        energy sub-objects reflecting the lifestyle shift.
    """
    sim_inputs: Dict[str, Any] = {
        "transport": base["transport"].copy(),
        "energy": base["energy"].copy(),
        "food": base["food"].copy(),
        "consumption": base["consumption"].copy(),
    }

    # Shift a fraction of gasoline km to public transit
    gas_car = base["transport"]["gas_car_km"]
    shifted_km = gas_car * transit_shift_ratio
    sim_inputs["transport"]["gas_car_km"] = max(0.0, gas_car - shifted_km)
    sim_inputs["transport"]["public_transit_km"] += shifted_km

    # Shift a fraction of grid kWh to clean/solar energy
    grid_kwh = base["energy"]["grid_kwh"]
    shifted_kwh = grid_kwh * energy_shift_ratio
    sim_inputs["energy"]["grid_kwh"] = max(0.0, grid_kwh - shifted_kwh)
    sim_inputs["energy"]["clean_kwh"] += shifted_kwh

    return sim_inputs


def _apply_dietary_reduction(
    sim_emissions: Dict[str, float],
    meat_reduction_ratio: float,
) -> Dict[str, float]:
    """Interpolate food emissions toward the vegan minimum based on reduction ratio.

    Because diet is a categorical variable (not a continuous slider), we model
    dietary reduction by linearly interpolating the food emission value between
    its current level and the minimum achievable level (vegan diet × MEALS_PER_MONTH).

    Args:
        sim_emissions: Emission dict as returned by ``calculate_category_emissions()``.
        meat_reduction_ratio: Fraction [0, 1] representing the desired dietary
            carbon reduction. ``1.0`` shifts fully to vegan-equivalent emissions.

    Returns:
        Dict[str, float]: Updated emissions dict with adjusted ``"food"`` and
        recalculated ``"total"`` values.
    """
    food_current = sim_emissions["food"]
    # The minimum achievable food emissions are the vegan diet level
    vegan_minimum = EMISSION_FACTORS["food"]["vegan"] * MEALS_PER_MONTH
    # Potential savings = current food carbon above the vegan floor
    potential_savings = max(0.0, food_current - vegan_minimum)
    # Apply the reduction ratio to estimate the new food emission level
    sim_emissions["food"] = round(food_current - (potential_savings * meat_reduction_ratio), 2)
    sim_emissions["total"] = round(
        sim_emissions["transport"]
        + sim_emissions["energy"]
        + sim_emissions["food"]
        + sim_emissions["consumption"],
        2,
    )
    return sim_emissions
