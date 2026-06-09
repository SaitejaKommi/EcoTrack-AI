"""
Gemini AI Coach and Prediction Service for CarbonWise AI.

Interfaces with the Google Gemini Generative AI API to produce three types
of personalised AI outputs:

1. **Coaching Insights**: Data-driven insights, explainable action suggestions,
   and weekly goal recommendations tailored to the user's specific footprint.
2. **Future Predictions**: 30-day and 90-day carbon trajectory forecasts based
   on the user's historical calculation records.
3. **Action Plans**: Structured daily, weekly, and monthly habit checklists
   prioritised by impact, difficulty, and cost.

All three methods implement a time-to-live (TTL) in-memory cache to avoid
redundant API calls when the same footprint data is requested within the
cache window. When the Gemini API is unavailable or unconfigured, a local
rules-based fallback engine generates contextually relevant responses that
match the same JSON schema expected from the API.

Architecture role: External integration / service layer — wraps all Gemini
API complexity behind a clean static interface. Route handlers never interact
with the ``google.generativeai`` client directly.

Typical usage:
    from app.services.gemini_service import GeminiService
    insights = GeminiService.generate_coaching_insights(user_id, footprint)
    plan = GeminiService.generate_action_plan(user_id, footprint)
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import google.generativeai as genai

from app.config import Config
from app.constants import (
    AI_CACHE_TTL_SECONDS,
    EMISSION_FACTORS,
    GEMINI_MODEL_NAME,
    MEALS_PER_MONTH,
    PREDICTION_HISTORY_LIMIT,
)

logger = logging.getLogger(__name__)


class GeminiService:
    """Service class wrapping the Google Gemini Generative AI API.

    Uses class-level attributes to maintain a single API initialisation state
    and shared TTL caches across all requests without requiring a database.

    Attributes:
        _initialized: Flag indicating whether the Gemini client has been configured.
        _insights_cache: TTL cache mapping footprint keys to coaching insight dicts.
        _action_plan_cache: TTL cache mapping footprint keys to action plan dicts.
    """

    _initialized: bool = False

    # In-memory TTL cache — maps cache key string to (timestamp, cached_value) tuple
    _insights_cache: Dict[str, tuple] = {}
    _action_plan_cache: Dict[str, tuple] = {}

    @classmethod
    def _make_cache_key(cls, user_id: str, footprint: Dict[str, Any]) -> str:
        """Generate a deterministic string cache key from user and footprint data.

        Serialises the relevant footprint fields as a sorted JSON string so
        that identical inputs always produce the same cache key regardless of
        dict insertion order.

        Args:
            user_id: Authenticated user identifier.
            footprint: Footprint document from the calculations collection.

        Returns:
            str: Stable JSON string used as the in-memory cache key.
        """
        key_data = {
            "user_id": user_id,
            "emissions": footprint.get("emissions", {}),
            "scores": footprint.get("category_scores", {}),
            "inputs": footprint.get("inputs", {}),
        }
        return json.dumps(key_data, sort_keys=True)

    @classmethod
    def _initialize_api(cls) -> bool:
        """Configure the Gemini API client if credentials are available.

        Reads the API key from ``Config.GEMINI_API_KEY`` and calls
        ``genai.configure()``. Sets ``Config.MOCK_MODE = True`` on any failure
        to prevent repeated configuration attempts.

        Returns:
            bool: ``True`` when the client is successfully configured and ready,
            ``False`` when credentials are missing or configuration failed.

        Raises:
            No exceptions — configuration errors are caught and logged.
        """
        if cls._initialized:
            return not Config.MOCK_MODE

        if not Config.GEMINI_API_KEY or not Config.GEMINI_API_KEY.strip():
            Config.MOCK_MODE = True
            return False

        try:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            cls._initialized = True
            logger.info("[AI] Gemini API configured successfully.")
            return True
        except Exception as exc:
            logger.error("[AI] Failed to configure Gemini API client: %s.", exc)
            Config.MOCK_MODE = True
            return False

    @classmethod
    def _parse_ai_json(cls, text: str) -> Optional[Dict[str, Any]]:
        """Parse a JSON response from the Gemini model, stripping markdown wrappers.

        The model sometimes wraps its JSON in triple-backtick code fences;
        this method strips those before attempting to deserialise.

        Args:
            text: Raw string response from ``model.generate_content()``.

        Returns:
            Optional[Dict[str, Any]]: Parsed dictionary when the text is valid
            JSON, or ``None`` when parsing fails.

        Raises:
            No exceptions — parse errors are caught and logged.
        """
        try:
            cleaned = text.strip()
            # Remove opening ``` or ```json fence
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            # Remove closing ``` fence
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("\n", 1)[0]
            # Remove stray "json" prefix if present without backticks
            if cleaned.startswith("json"):
                cleaned = cleaned.split("json", 1)[1]
            return json.loads(cleaned.strip())
        except Exception as exc:
            logger.error(
                "[AI] JSON parse failed. Raw snippet: %s… Error: %s",
                text[:200],
                exc,
            )
            return None

    @classmethod
    def _get_cached(
        cls, cache: Dict[str, tuple], key: str
    ) -> Optional[Any]:
        """Return a cached value if it exists and has not expired.

        Args:
            cache: The target cache dict (insights or action plan).
            key: Cache key to look up.

        Returns:
            Optional[Any]: Cached value when fresh, or ``None`` when the
            cache is empty or the entry has exceeded ``AI_CACHE_TTL_SECONDS``.
        """
        if key in cache:
            cached_at, cached_val = cache[key]
            if time.time() - cached_at < AI_CACHE_TTL_SECONDS:
                return cached_val
        return None

    @classmethod
    def generate_coaching_insights(
        cls, user_id: str, footprint: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request personalised sustainability coaching insights from Gemini.

        Builds a detailed contextual prompt including the user's transport,
        energy, food, and consumption data, then requests structured JSON
        containing insights, explainable suggestions, and weekly goals.
        Returns the cached response when the same footprint is requested again
        within the TTL window.

        Args:
            user_id: Authenticated user identifier (used for cache keying and
                logging).
            footprint: Latest calculation document from the database, containing
                ``"emissions"``, ``"category_scores"``, ``"eco_score"``, and
                ``"inputs"`` fields.

        Returns:
            Dict[str, Any]: Coaching response containing:
                - ``"insights"``: List of 3 data-driven insight strings.
                - ``"suggestions"``: List of 3 explainable suggestion objects.
                - ``"weekly_goals"``: List of 3 interactive goal objects.
            Falls back to the local mock coach when the API is unavailable.

        Raises:
            No exceptions — API failures trigger silent fallback.
        """
        key = cls._make_cache_key(user_id, footprint)
        cached = cls._get_cached(cls._insights_cache, key)
        if cached:
            logger.debug("[AI] Cache hit — coaching insights for user %s.", user_id)
            return cached

        emissions = footprint.get("emissions", {})
        scores = footprint.get("category_scores", {})
        total_score = footprint.get("eco_score", 50.0)
        inputs = footprint.get("inputs", {})
        username = footprint.get("username", "Eco Tracker")

        result = None
        if cls._initialize_api():
            result = cls._call_insights_api(username, emissions, scores, total_score, inputs)

        if not result:
            result = cls._get_mock_coaching(emissions, scores, inputs)

        cls._insights_cache[key] = (time.time(), result)
        return result

    @classmethod
    def _call_insights_api(
        cls,
        username: str,
        emissions: Dict[str, float],
        scores: Dict[str, float],
        total_score: float,
        inputs: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Execute the Gemini API call for coaching insights.

        Constructs a structured prompt with the user's footprint data and
        requested JSON schema, then parses the model's response.

        Args:
            username: User's display name injected into the prompt.
            emissions: Per-category emission values in kg CO2e.
            scores: Per-category eco scores (0–100).
            total_score: Overall eco score.
            inputs: Raw activity inputs (transport km, diet, etc.).

        Returns:
            Optional[Dict[str, Any]]: Parsed coaching dict on success, or
            ``None`` when the API call or JSON parsing fails.
        """
        prompt = _build_insights_prompt(username, emissions, scores, total_score, inputs)
        try:
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            response = model.generate_content(prompt)
            return cls._parse_ai_json(response.text)
        except Exception as exc:
            logger.error("[AI] Gemini insights API call failed: %s.", exc)
            return None

    @classmethod
    def predict_future_footprint(
        cls, user_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Predict 30-day and 90-day emission trajectories using historical data.

        Sends the last ``PREDICTION_HISTORY_LIMIT`` footprint records to Gemini
        and requests a forward projection. Falls back to a local linear trend
        extrapolation when the API is unavailable.

        Args:
            user_history: List of historical footprint documents ordered
                newest-first. Each item must contain ``"created_at"``,
                ``"emissions.total"``, and ``"eco_score"`` fields.

        Returns:
            Dict[str, Any]: Prediction containing:
                - ``"projection_30_days"``: float, estimated total kg CO2e next month.
                - ``"projection_90_days"``: float, estimated total kg CO2e in 3 months.
                - ``"reasoning"``: str, human-readable explanation of the forecast.

        Raises:
            No exceptions — API failures trigger the local fallback.
        """
        if not user_history:
            return _empty_prediction()

        hist_summary = _build_history_summary(user_history)
        latest_total = hist_summary[0]["total"]

        if cls._initialize_api():
            result = cls._call_prediction_api(hist_summary)
            if result:
                return result

        return _linear_trend_prediction(hist_summary, latest_total)

    @classmethod
    def _call_prediction_api(
        cls, hist_summary: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Execute the Gemini API call for footprint prediction.

        Args:
            hist_summary: Condensed history list with ``"date"``, ``"total"``,
                and ``"score"`` fields.

        Returns:
            Optional[Dict[str, Any]]: Parsed prediction dict on success, or
            ``None`` when the API call or JSON parsing fails.
        """
        prompt = _build_prediction_prompt(hist_summary)
        try:
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            response = model.generate_content(prompt)
            return cls._parse_ai_json(response.text)
        except Exception as exc:
            logger.error("[AI] Gemini prediction API call failed: %s.", exc)
            return None

    @classmethod
    def generate_action_plan(
        cls, user_id: str, footprint: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a prioritised daily, weekly, and monthly habit action plan.

        Sends the user's current emission levels to Gemini and requests a
        structured JSON action plan. Caches the response for ``AI_CACHE_TTL_SECONDS``
        seconds to avoid repeated API calls for the same footprint.

        Args:
            user_id: Authenticated user identifier.
            footprint: Latest calculation document from the database.

        Returns:
            Dict[str, Any]: Action plan containing:
                - ``"daily"``: List of 2 small daily habit actions.
                - ``"weekly"``: List of 2 medium weekly habit actions.
                - ``"monthly"``: List of 2 larger monthly structural changes.
            Each action has ``"task"``, ``"impact"``, ``"difficulty"``,
            ``"cost"``, and ``"category"`` keys.

        Raises:
            No exceptions — API failures trigger the local fallback.
        """
        key = cls._make_cache_key(user_id, footprint)
        cached = cls._get_cached(cls._action_plan_cache, key)
        if cached:
            logger.debug("[AI] Cache hit — action plan for user %s.", user_id)
            return cached

        emissions = footprint.get("emissions", {})
        result = None
        if cls._initialize_api():
            result = cls._call_action_plan_api(emissions)

        if not result:
            result = cls._get_mock_action_plan(emissions)

        cls._action_plan_cache[key] = (time.time(), result)
        return result

    @classmethod
    def _call_action_plan_api(
        cls, emissions: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Execute the Gemini API call for action plan generation.

        Args:
            emissions: Per-category emission values in kg CO2e.

        Returns:
            Optional[Dict[str, Any]]: Parsed action plan dict on success, or
            ``None`` when the API call or JSON parsing fails.
        """
        prompt = _build_action_plan_prompt(emissions)
        try:
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            response = model.generate_content(prompt)
            return cls._parse_ai_json(response.text)
        except Exception as exc:
            logger.error("[AI] Gemini action plan API call failed: %s.", exc)
            return None

    @classmethod
    def _get_mock_coaching(
        cls,
        emissions: Dict[str, float],
        scores: Dict[str, float],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate data-driven coaching insights locally without the Gemini API.

        Applies rule-based logic to the user's transport distance, grid energy
        usage, and diet type to produce contextually relevant insights and
        suggestions that match the same schema as the Gemini API response.

        Args:
            emissions: Per-category emission values in kg CO2e.
            scores: Per-category eco scores (0–100).
            inputs: Raw activity inputs from the calculator submission.

        Returns:
            Dict[str, Any]: Mock coaching response with ``"insights"``,
            ``"suggestions"``, and ``"weekly_goals"`` keys.
        """
        gas_car_km = inputs.get("transport", {}).get("gas_car_km", 0.0)
        grid_kwh = inputs.get("energy", {}).get("grid_kwh", 0.0)
        diet = inputs.get("food", {}).get("diet", "balanced")

        insights, suggestions = _build_mock_insights_and_suggestions(gas_car_km, grid_kwh, diet)

        # Ensure exactly 3 items in each list by padding with generic fallbacks
        while len(insights) < 3:
            insights.append("Your consumption profile indicates balanced shopping practices.")
        while len(suggestions) < 3:
            suggestions.append("Repurpose or recycle older materials to close consumption waste loops.")

        return {
            "insights": insights[:3],
            "suggestions": _build_suggestion_objects(suggestions[:3]),
            "weekly_goals": _get_default_weekly_goals(),
        }

    @classmethod
    def _get_mock_action_plan(
        cls, emissions: Dict[str, float]
    ) -> Dict[str, Any]:
        """Return a static fallback action plan when the Gemini API is unavailable.

        Args:
            emissions: Per-category emission values (not used by the static
                fallback but included for API consistency).

        Returns:
            Dict[str, Any]: Fallback action plan with ``"daily"``, ``"weekly"``,
            and ``"monthly"`` action lists.
        """
        return {
            "daily": [
                {
                    "task": "Unplug standby devices and electronics at night",
                    "impact": "Low",
                    "difficulty": "Easy",
                    "cost": "Free",
                    "category": "energy",
                },
                {
                    "task": "Walk or bike for short trips under 2 kilometres",
                    "impact": "Medium",
                    "difficulty": "Easy",
                    "cost": "Free",
                    "category": "transport",
                },
            ],
            "weekly": [
                {
                    "task": "Commit to 3 fully plant-based meatless days",
                    "impact": "High",
                    "difficulty": "Medium",
                    "cost": "Free",
                    "category": "food",
                },
                {
                    "task": "Consolidate grocery trips to reduce car mileage",
                    "impact": "Medium",
                    "difficulty": "Easy",
                    "cost": "Free",
                    "category": "transport",
                },
            ],
            "monthly": [
                {
                    "task": "Schedule energy audit and switch to LED bulbs",
                    "impact": "High",
                    "difficulty": "Easy",
                    "cost": "Low",
                    "category": "energy",
                },
                {
                    "task": "Purchase clothing from secondhand or thrift shops only",
                    "impact": "Medium",
                    "difficulty": "Medium",
                    "cost": "Low",
                    "category": "consumption",
                },
            ],
        }


# ─── Private Prompt Builder Functions ─────────────────────────────────────────


def _build_insights_prompt(
    username: str,
    emissions: Dict[str, float],
    scores: Dict[str, float],
    total_score: float,
    inputs: Dict[str, Any],
) -> str:
    """Construct the Gemini prompt for personalised coaching insights.

    Args:
        username: User's display name for personalisation.
        emissions: Per-category emission values in kg CO2e.
        scores: Per-category eco scores (0–100).
        total_score: Overall eco score.
        inputs: Activity inputs (transport, energy, food, consumption).

    Returns:
        str: Complete prompt string ready to send to the Gemini model.
    """
    t_inputs = inputs.get("transport", {})
    e_inputs = inputs.get("energy", {})
    return f"""
You are an expert Sustainability Coach. Analyse the carbon footprint of the user {username}.
Monthly footprint data:
- Total Carbon Footprint: {emissions.get('total', 0)} kg CO2e
- Transport: {emissions.get('transport', 0)} kg CO2e (Score: {scores.get('transport', 50)}/100)
- Energy: {emissions.get('energy', 0)} kg CO2e (Score: {scores.get('energy', 50)}/100)
- Food: {emissions.get('food', 0)} kg CO2e (Score: {scores.get('food', 50)}/100)
- Consumption: {emissions.get('consumption', 0)} kg CO2e (Score: {scores.get('consumption', 50)}/100)
- Overall Eco Score: {total_score}/100

Specific habits:
- Diet: {inputs.get('food', {}).get('diet', 'balanced')}
- Shopping: {inputs.get('consumption', {}).get('shopping_habit', 'average_shopper')}
- Gas Car: {t_inputs.get('gas_car_km', 0)} km, EV: {t_inputs.get('electric_car_km', 0)} km, Transit: {t_inputs.get('public_transit_km', 0)} km, Flights: {t_inputs.get('flight_km', 0)} km
- Grid: {e_inputs.get('grid_kwh', 0)} kWh, Clean: {e_inputs.get('clean_kwh', 0)} kWh

Generate a JSON object with:
1. "insights": list of 3 detailed user-specific insights.
2. "suggestions": list of 3 objects each with "text", "why_chosen", "estimated_impact", "expected_outcome".
3. "weekly_goals": list of 3 objects each with "title", "description", "impact" (High/Medium/Low), "points" (10-30).

Response MUST be raw valid JSON only.
"""


def _build_prediction_prompt(hist_summary: List[Dict[str, Any]]) -> str:
    """Construct the Gemini prompt for footprint trajectory prediction.

    Args:
        hist_summary: Condensed history list newest-first.

    Returns:
        str: Complete prompt string ready to send to the Gemini model.
    """
    return f"""
You are a carbon footprint predictive forecaster. Based on the user's history (newest first):
{json.dumps(hist_summary, indent=2)}

Generate a JSON object with:
1. "projection_30_days": Predicted total emissions (kg CO2e) for next month.
2. "projection_90_days": Predicted total emissions (kg CO2e) for 3 months from now.
3. "reasoning": A 2-sentence explanation of the projection trend.

Response MUST be raw valid JSON only.
"""


def _build_action_plan_prompt(emissions: Dict[str, float]) -> str:
    """Construct the Gemini prompt for action plan generation.

    Args:
        emissions: Per-category emission values in kg CO2e.

    Returns:
        str: Complete prompt string ready to send to the Gemini model.
    """
    return f"""
You are an AI Smart Action Planner for CarbonWise AI.
Create a customised action plan for monthly emissions (kg CO2e):
- Transport: {emissions.get('transport', 0)}
- Energy: {emissions.get('energy', 0)}
- Food: {emissions.get('food', 0)}
- Consumption: {emissions.get('consumption', 0)}

Categories: "daily" (2 small habits), "weekly" (2 medium), "monthly" (2 structural).
Each action: "task", "impact" (High/Medium/Low), "difficulty" (Easy/Medium/Hard), "cost" (Free/Low/Moderate/High), "category".

Response MUST be raw valid JSON only.
"""


# ─── Private Fallback Helper Functions ────────────────────────────────────────


def _build_history_summary(
    user_history: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Condense user history into a minimal summary for Gemini prompts.

    Args:
        user_history: Full footprint documents from the database, newest first.

    Returns:
        List[Dict[str, Any]]: Condensed list of at most PREDICTION_HISTORY_LIMIT
        items, each with ``"date"``, ``"total"``, and ``"score"`` keys.
    """
    summary = []
    for entry in user_history[:PREDICTION_HISTORY_LIMIT]:
        summary.append({
            "date": entry.get("created_at", "")[:10],
            "total": entry.get("emissions", {}).get("total", 0.0),
            "score": entry.get("eco_score", 50.0),
        })
    return summary


def _empty_prediction() -> Dict[str, Any]:
    """Return a zero-value prediction result when no history is available.

    Returns:
        Dict[str, Any]: Prediction dict with all numeric values at 0.
    """
    return {
        "projection_30_days": 0.0,
        "projection_90_days": 0.0,
        "reasoning": "No history available to analyse future carbon trends.",
    }


def _linear_trend_prediction(
    hist_summary: List[Dict[str, Any]],
    latest_total: float,
) -> Dict[str, Any]:
    """Generate a forward projection using a simple linear trend extrapolation.

    Computes the average change between the newest and oldest record in the
    summary window and extrapolates that slope forward by 1 and 3 months.

    Args:
        hist_summary: Condensed history summary with ``"total"`` fields.
        latest_total: Most recent total emission value (kg CO2e).

    Returns:
        Dict[str, Any]: Linear trend prediction with 30-day and 90-day projections.
    """
    trend = 0.0
    if len(hist_summary) > 1:
        # Slope = (newest total − oldest total) / number of intervals
        trend = (hist_summary[0]["total"] - hist_summary[-1]["total"]) / len(hist_summary)

    proj_30 = max(0.0, latest_total + trend)
    proj_90 = max(0.0, latest_total + (trend * 3.0))

    direction = "shrinking" if trend < 0 else "expanding" if trend > 0 else "remaining stable"
    return {
        "projection_30_days": round(proj_30, 2),
        "projection_90_days": round(proj_90, 2),
        "reasoning": (
            f"Based on your recent logs, your emissions are {direction}. "
            "Shifting habits will help lock in long-term savings."
        ),
    }


def _build_mock_insights_and_suggestions(
    gas_car_km: float,
    grid_kwh: float,
    diet: str,
) -> tuple:
    """Generate rule-based insights and suggestions from user activity values.

    Args:
        gas_car_km: Monthly gasoline car distance in kilometres.
        grid_kwh: Monthly grid electricity consumption in kWh.
        diet: Diet type string (e.g. ``"meat_heavy"``, ``"vegan"``).

    Returns:
        Tuple[List[str], List[str]]: Parallel lists of insight strings and
        suggestion strings of equal length.
    """
    # Threshold: gas car trips above 300 km/month are considered high-impact
    _GAS_CAR_HIGH_THRESHOLD = 300.0
    # Threshold: grid usage above 200 kWh/month is a meaningful reduction opportunity
    _GRID_HIGH_THRESHOLD = 200.0

    insights: List[str] = []
    suggestions: List[str] = []

    if gas_car_km > _GAS_CAR_HIGH_THRESHOLD:
        insights.append("Your gasoline car commuting accounts for a significant portion of your transit emissions.")
        suggestions.append("Consider grouping errands or carpooling to reduce monthly gas car miles by 20%.")
    else:
        insights.append("Your commuting footprint is relatively light, showing effective transit optimization.")
        suggestions.append("Check if walking or cycling is viable for short trips under 2 km.")

    if grid_kwh > _GRID_HIGH_THRESHOLD:
        insights.append("Grid-sourced electrical power represents a core decarbonisation opportunity in your profile.")
        suggestions.append("Investigate local community solar options or smart plug monitors to curb phantom electricity load.")
    else:
        insights.append("Your domestic electricity consumption is efficiently maintained.")
        suggestions.append("Try installing LED bulbs throughout your workspace to squeeze out further energy efficiencies.")

    if diet == "meat_heavy":
        insights.append("A meat-heavy diet multiplies your dietary carbon footprint by up to 7 times compared to plant alternatives.")
        suggestions.append("Implement a 'Meatless Mondays' routine to transition some meals to vegetarian or vegan recipes.")
    else:
        insights.append("Your plant-inclined diet significantly curbs food-related carbon emissions.")
        suggestions.append("Prioritise buying locally grown, seasonal foods to reduce transit-mile food footprints.")

    return insights, suggestions


def _build_suggestion_objects(suggestions: List[str]) -> List[Dict[str, Any]]:
    """Wrap raw suggestion strings into the explainable suggestion schema.

    Assigns contextually relevant ``why_chosen``, ``estimated_impact``, and
    ``expected_outcome`` values based on keyword matching in the suggestion text.

    Args:
        suggestions: List of raw suggestion strings from the mock coach.

    Returns:
        List[Dict[str, Any]]: List of suggestion objects matching the Gemini
        API schema with ``"text"``, ``"why_chosen"``, ``"estimated_impact"``,
        and ``"expected_outcome"`` keys.
    """
    result = []
    for sug in suggestions:
        why = "Chosen because this category represents a significant portion of your footprint."
        impact = "15-30 kg CO2e saved/mo"
        outcome = "Decreased utility costs and lower household resource consumption."

        # Transport-related suggestions are identified by commute and mileage keywords
        if any(kw in sug for kw in ("miles", "errands", "commute", "cycling", "carpooling")):
            why = "Chosen to reduce petroleum consumption in your daily commutes."
            impact = "40-80 kg CO2e saved/mo"
            outcome = "Reduced fuel expenses and lowered transportation carbon load."
        # Energy-related suggestions are identified by renewable and efficiency keywords
        elif any(kw in sug for kw in ("solar", "LED", "plug", "electricity")):
            why = "Chosen to transition domestic grid loads to renewable sources."
            impact = "30-50 kg CO2e saved/mo"
            outcome = "Reduced energy bills and cleaner home power footprint."
        # Diet-related suggestions are identified by food and dietary choice keywords
        elif any(kw in sug for kw in ("diet", "meat-free", "vegan", "Mondays", "seasonal", "plant")):
            why = "Chosen to substitute high-carbon beef meals with plant proteins."
            impact = "20-40 kg CO2e saved/mo"
            outcome = "Better personal health and lower dietary resource usage."

        result.append({
            "text": sug,
            "why_chosen": why,
            "estimated_impact": impact,
            "expected_outcome": outcome,
        })
    return result


def _get_default_weekly_goals() -> List[Dict[str, Any]]:
    """Return the standard set of three weekly goals for the mock coach.

    Returns:
        List[Dict[str, Any]]: Three goal objects with ``"title"``,
        ``"description"``, ``"impact"``, and ``"points"`` keys.
    """
    return [
        {
            "title": "Clean Energy Switch",
            "description": "Switch to renewable grid tariffs or shut off appliances completely when not in use.",
            "impact": "Medium",
            "points": 15,
        },
        {
            "title": "Low Emission Travel",
            "description": "Replace one gas-car commute with public transit, bicycling, or carpooling this week.",
            "impact": "High",
            "points": 25,
        },
        {
            "title": "Plant-Forward Day",
            "description": "Prepare fully meat-free plant meals for an entire day to reduce resource footprint.",
            "impact": "Medium",
            "points": 20,
        },
    ]
