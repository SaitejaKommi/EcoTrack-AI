"""
Constants Module for CarbonWise AI.

Centralizes all business logic constants, emission factors, scoring weights,
validation limits, caching parameters, and gamification thresholds into a
single source of truth. All modules must import from here rather than using
hardcoded literal values.

Architecture role: This module is a pure data layer with no dependencies on
other application modules. It must remain importable in isolation.

Typical usage:
    from app.constants import EMISSION_FACTORS, CATEGORY_BASELINES
    transport_kg = distance_km * EMISSION_FACTORS["transport"]["gas_car"]
"""

from typing import Dict

# ============================================================
# EMISSION FACTORS (kg CO2e per unit)
# Values sourced from EPA and IPCC 2023 methodology guidelines.
# ============================================================

EMISSION_FACTORS: Dict[str, Dict[str, float]] = {
    "transport": {
        "gas_car": 0.220,        # Per km — average petrol/gasoline passenger vehicle
        "electric_car": 0.050,   # Per km — grid-charged EV (average grid carbon intensity)
        "public_transit": 0.040, # Per km — mixed bus and rail average
        "flight": 0.180          # Per km — short and long haul aviation average
    },
    "energy": {
        "grid_electricity": 0.475, # Per kWh — average national grid carbon intensity
        "clean_energy": 0.020      # Per kWh — solar/wind/hydro lifecycle emissions
    },
    "food": {
        "meat_heavy": 3.0,    # Per meal — high red meat consumption
        "balanced": 1.5,      # Per meal — mixed diet with moderate meat
        "vegetarian": 0.8,    # Per meal — plant-based with dairy and eggs
        "vegan": 0.4          # Per meal — fully plant-based diet
    },
    "consumption": {
        "high_shopper": 150.0,   # Per month — frequent fashion and electronics purchases
        "average_shopper": 75.0, # Per month — typical Western consumer
        "minimalist": 15.0       # Per month — minimal discretionary spending
    }
}

# ============================================================
# ECO SCORE THRESHOLDS AND WEIGHTS
# Weights must sum to 1.0 (100%).
# ============================================================

# Eco Score category weighting distribution
SCORE_WEIGHTS: Dict[str, float] = {
    "transport": 0.35,   # 35% — highest weight, largest individual impact
    "energy": 0.30,      # 30% — home energy use is the next largest factor
    "food": 0.20,        # 20% — dietary carbon is substantial but reducible
    "consumption": 0.15  # 15% — discretionary purchases have lower but meaningful impact
}

# Average Western European/US per-capita monthly baseline (kg CO2e)
# Score of 50 means user matches this baseline exactly.
CATEGORY_BASELINES: Dict[str, float] = {
    "transport": 450.0,   # Monthly average transport carbon
    "energy": 350.0,      # Monthly average home energy carbon
    "food": 250.0,        # Monthly average food carbon
    "consumption": 180.0  # Monthly average consumption carbon
}

# Eco score tiers for UI descriptions
ECO_SCORE_HIGH_THRESHOLD: float = 80.0   # Score >= 80: Outstanding sustainability habits
ECO_SCORE_AVERAGE_THRESHOLD: float = 50.0 # Score >= 50: Better than average baseline

# ============================================================
# ACHIEVEMENT THRESHOLDS
# Minimum values required to earn gamification badges.
# ============================================================

# Minimum clean-travel share to earn Transit Hero badge (80% of travel must be EV/transit)
CLEAN_TRAVEL_BADGE_THRESHOLD: float = 0.8

# Minimum clean-energy share to earn Energy Wizard badge (80% of energy from clean sources)
CLEAN_ENERGY_BADGE_THRESHOLD: float = 0.8

# Minimum eco score to earn Eco Warrior badge (overall score >= 85)
ECO_WARRIOR_BADGE_THRESHOLD: float = 85.0

# Minimum consecutive-day streak to earn Habit Builder badge
STREAK_BUILDER_BADGE_THRESHOLD: int = 7

# ============================================================
# CARBON CALCULATION CONSTANTS
# ============================================================

# Standard meals consumed per month per person (3 meals/day * 30 days)
MEALS_PER_MONTH: float = 90.0

# Default food emission fallback when diet type is unrecognized
DEFAULT_MEAT_DIET_EMISSIONS: float = 1.5  # kg CO2e per meal — falls back to "balanced"

# Default consumption emission fallback when shopping type is unrecognized
DEFAULT_AVERAGE_SHOPPER_EMISSIONS: float = 75.0  # kg CO2e per month

# Eco score linear scaling: score = OFFSET - (emissions / baseline) * MULTIPLIER
SCORE_SCALING_OFFSET: float = 100.0     # Maximum score achievable
SCORE_SCALING_MULTIPLIER: float = 50.0  # Scaling sensitivity factor

# ============================================================
# INPUT VALIDATION LIMITS
# ============================================================

# Maximum km per month for any single transport mode before rejection
TRANSPORT_KM_MAX_LIMIT: float = 100_000.0  # Prevents DoS through overflow attacks

# Maximum kWh per month for any single energy source before rejection
ENERGY_KWH_MAX_LIMIT: float = 50_000.0     # Practical upper bound for residential energy

# User registration input length boundaries
USERNAME_MIN_LENGTH: int = 3    # At least 3 characters for readability
USERNAME_MAX_LENGTH: int = 30   # Capped to prevent database bloat
EMAIL_MAX_LENGTH: int = 60      # Standard email max-length recommendation
PASSWORD_MIN_LENGTH: int = 6    # Minimum viable brute-force resistance
PASSWORD_MAX_LENGTH: int = 100  # Bcrypt input length safety cap

# ============================================================
# RATE LIMITING
# Limits are enforced per client IP address via Flask-Limiter.
# ============================================================

# Global rate limit applied to all API endpoints (broad protection)
RATE_LIMIT_HOURLY: str = "100 per hour"

# Per-minute rate limit to prevent rapid-fire spam attacks
RATE_LIMIT_MINUTELY: str = "10 per minute"

# ============================================================
# CACHE CONFIGURATION
# In-memory caching for expensive Gemini API calls.
# ============================================================

# Time-to-live for cached coaching insights and action plans (seconds)
AI_CACHE_TTL_SECONDS: int = 600  # 10 minutes — balances freshness with API cost

# Maximum number of historical records used for predictive forecasting
PREDICTION_HISTORY_LIMIT: int = 5  # Last 5 entries provide sufficient trend signal

# ============================================================
# GEMINI API CONFIGURATION
# ============================================================

# Gemini model name used for all generative AI requests
GEMINI_MODEL_NAME: str = "gemini-1.5-flash"

# ============================================================
# UI CONFIGURATION CONSTANTS (referenced from frontend)
# ============================================================

# Debounce delay for simulator slider inputs (milliseconds)
SIMULATOR_DEBOUNCE_MS: int = 250  # Prevents excessive API calls during rapid slider movement

# Accessibility font scaling boundaries (percentage of default font size)
FONT_SIZE_MAX_PCT: int = 140   # Maximum font scaling — 140% of default
FONT_SIZE_MIN_PCT: int = 80    # Minimum font scaling — 80% of default
FONT_SIZE_STEP_PCT: int = 10   # Increment/decrement step per button press
FONT_SIZE_DEFAULT_PCT: int = 100  # Default baseline font size percentage

# Screen reader announcement delay (milliseconds)
A11Y_ANNOUNCE_DELAY_MS: int = 100  # Ensures layout settles before ARIA update fires

# Goal carbon savings estimates by impact tier (kg CO2e)
GOAL_CARBON_HIGH_IMPACT: float = 25.0   # High impact goal completion
GOAL_CARBON_MEDIUM_IMPACT: float = 12.0  # Medium impact goal completion
GOAL_CARBON_LOW_IMPACT: float = 5.0     # Low impact goal completion

# ============================================================
# GAMIFICATION BADGE CONFIGURATIONS
# ============================================================

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
