"""
Constants Module for CarbonWise AI.
Contains carbon emission coefficients, score weight distributions, and configuration limits.
"""

from typing import Dict

# Emission Factors (in kg CO2e per unit)
# Standard coefficients based on EPA and IPCC guidelines
EMISSION_FACTORS: Dict[str, Dict[str, float]] = {
    "transport": {
        "gas_car": 0.220,     # per km (average petrol car)
        "electric_car": 0.050,# per km (grid charging average)
        "public_transit": 0.040, # per km (bus/train average)
        "flight": 0.180       # per km (average short/long haul mix)
    },
    "energy": {
        "grid_electricity": 0.475, # per kWh
        "clean_energy": 0.020      # per kWh (solar/wind/hydro lifecycle)
    },
    "food": {
        "meat_heavy": 3.0,    # per meal
        "balanced": 1.5,      # per meal
        "vegetarian": 0.8,    # per meal
        "vegan": 0.4          # per meal
    },
    "consumption": {
        "high_shopper": 150.0, # per month (frequent fashion/electronics)
        "average_shopper": 75.0, # per month
        "minimalist": 15.0     # per month
    }
}

# Eco Score Weighting (Must sum to 100)
SCORE_WEIGHTS: Dict[str, float] = {
    "transport": 0.35,      # 35%
    "energy": 0.30,         # 30%
    "food": 0.20,           # 20%
    "consumption": 0.15     # 15%
}

# Baseline emissions per category for calculating the 0-100 Eco Score.
# Based on average Western European/US per capita emissions per month (in kg CO2e).
CATEGORY_BASELINES: Dict[str, float] = {
    "transport": 450.0,    # average monthly transport carbon
    "energy": 350.0,       # average monthly home energy carbon
    "food": 250.0,         # average monthly food carbon
    "consumption": 180.0   # average monthly purchases carbon
}

# Gamification Badge Configurations
BADGE_CONFIGS: Dict[str, Dict[str, str]] = {
    "transit_hero": {
        "title": "Transit Pioneer",
        "description": "Utilize public transit or electric vehicles for at least 80% of travel.",
        "icon": "bus-front-fill"
    },
    "green_diet": {
        "title": "Meatless Maestro",
        "description": "Adopt a vegetarian or vegan lifestyle for lower carbon food footprint.",
        "icon": "egg-fried"
    },
    "energy_wizard": {
        "title": "Eco-Volt",
        "description": "Transition home electricity usage to clean/solar sources.",
        "icon": "lightning-charge-fill"
    },
    "eco_warrior": {
        "title": "Eco Warrior",
        "description": "Achieve a total Eco Score of 85 or above.",
        "icon": "shield-check"
    },
    "streak_master": {
        "title": "Habit Builder",
        "description": "Maintain a calculation or goal streak of 7 days or more.",
        "icon": "fire"
    }
}

# --- BUSINESS CALCULATION CONSTANTS ---
# Standard multiplier constants
MEALS_PER_MONTH: float = 90.0
DEFAULT_MEAT_DIET_EMISSIONS: float = 1.5
DEFAULT_AVERAGE_SHOPPER_EMISSIONS: float = 75.0

# Eco score scaling factors
SCORE_SCALING_OFFSET: float = 100.0
SCORE_SCALING_MULTIPLIER: float = 50.0

# Gamification and badge threshold margins
CLEAN_TRAVEL_BADGE_THRESHOLD: float = 0.8
CLEAN_ENERGY_BADGE_THRESHOLD: float = 0.8
ECO_WARRIOR_BADGE_THRESHOLD: float = 85.0
STREAK_BUILDER_BADGE_THRESHOLD: int = 7

