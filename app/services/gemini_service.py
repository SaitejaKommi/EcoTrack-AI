"""
Gemini AI Coach & Prediction Service for CarbonWise AI.
Communicates with the Google Gemini Generative AI API to produce personalized
coaching reviews, future forecasts, and prioritized action checklists.
"""

import json
import time
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from app.config import Config
from app.db import get_db

class GeminiService:
    """Service class interfacing with Google Gemini AI."""
    
    _initialized = False
    
    # Cache fields for performance optimization (Phase 8: Performance Caching)
    _insights_cache: Dict[str, tuple] = {}
    _action_plan_cache: Dict[str, tuple] = {}
    _CACHE_TTL = 300  # 5 minutes in seconds

    @classmethod
    def _make_cache_key(cls, user_id: str, footprint: Dict[str, Any]) -> str:
        """Generates a unique deterministic string representing user footprint data."""
        data_to_hash = {
            "user_id": user_id,
            "emissions": footprint.get("emissions", {}),
            "scores": footprint.get("category_scores", {}),
            "inputs": footprint.get("inputs", {})
        }
        return json.dumps(data_to_hash, sort_keys=True)

    @classmethod
    def _initialize_api(cls) -> bool:
        """Initializes the Gemini client if credentials are provided."""
        if cls._initialized:
            return not Config.MOCK_MODE
            
        if Config.GEMINI_API_KEY and Config.GEMINI_API_KEY.strip() != "":
            try:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                cls._initialized = True
                print("[AI] Gemini Generative AI API configured successfully.")
                return True
            except Exception as e:
                print(f"[AI ERROR] Failed to configure Gemini API client ({e}). Mock fallback active.")
                Config.MOCK_MODE = True
                return False
        else:
            Config.MOCK_MODE = True
            return False

    @classmethod
    def _parse_ai_json(cls, text: str) -> Optional[Dict[str, Any]]:
        """Parses JSON content returned by the model, clearing potential markdown wrapping."""
        try:
            # Strip markdown code blocks if any
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("\n", 1)[0]
            if cleaned.startswith("json"):
                cleaned = cleaned.split("json", 1)[1]
            cleaned = cleaned.strip()
            return json.loads(cleaned)
        except Exception as e:
            print(f"[AI PARSE ERROR] Failed to parse JSON from response. Raw: {text[:200]}... Error: {e}")
            return None

    @classmethod
    def generate_coaching_insights(cls, user_id: str, footprint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Requests personalized sustainability coaching insights from Gemini.
        """
        key = cls._make_cache_key(user_id, footprint)
        now = time.time()
        if key in cls._insights_cache:
            t, cached_val = cls._insights_cache[key]
            if now - t < cls._CACHE_TTL:
                print(f"[AI CACHE] Cache hit for user coaching insights: {user_id}")
                return cached_val

        # Formulate prompt using actual user habits
        username = footprint.get("username", "Eco Tracker")
        emissions = footprint.get("emissions", {})
        scores = footprint.get("category_scores", {})
        total_score = footprint.get("eco_score", 50.0)
        inputs = footprint.get("inputs", {})
        
        prompt = f"""
        You are an expert Sustainability Coach. Analyze the carbon footprint of the user {username}.
        Here is their monthly footprint data:
        - Total Carbon Footprint: {emissions.get('total', 0)} kg CO2e
        - Transport Footprint: {emissions.get('transport', 0)} kg CO2e (Score: {scores.get('transport', 50)}/100)
        - Energy Footprint: {emissions.get('energy', 0)} kg CO2e (Score: {scores.get('energy', 50)}/100)
        - Food Footprint: {emissions.get('food', 0)} kg CO2e (Score: {scores.get('food', 50)}/100)
        - Consumption Footprint: {emissions.get('consumption', 0)} kg CO2e (Score: {scores.get('consumption', 50)}/100)
        - Overall Eco Score: {total_score}/100

        Specific habits:
        - Diet: {inputs.get('food', {}).get('diet', 'balanced')}
        - Shopping Habit: {inputs.get('consumption', {}).get('shopping_habit', 'average_shopper')}
        - Travel Details: Gasoline Car {inputs.get('transport', {}).get('gas_car_km', 0)} km, EV {inputs.get('transport', {}).get('electric_car_km', 0)} km, Transit {inputs.get('transport', {}).get('public_transit_km', 0)} km, Flights {inputs.get('transport', {}).get('flight_km', 0)} km
        - Energy Details: Grid {inputs.get('energy', {}).get('grid_kwh', 0)} kWh, Solar/Clean {inputs.get('energy', {}).get('clean_kwh', 0)} kWh

        Generate a JSON object containing:
        1. "insights": A list of 3 detailed, user-specific insights pointing out where they emit the most and why.
        2. "suggestions": A list of 3 custom, actionable objects based on their highest categories. Each object must contain:
           - "text": The suggestion task text.
           - "why_chosen": Explanation of why this action was selected based on the user's input habits.
           - "estimated_impact": Expected carbon reduction (e.g., "15-30 kg CO2e saved").
           - "expected_outcome": Expected positive lifestyle outcome.
        3. "weekly_goals": A list of 3 interactive, short-term tasks. Each goal must have:
           - "title": short name
           - "description": specific action
           - "impact": "High", "Medium", or "Low"
           - "points": numeric score reward between 10 and 30 based on impact.

        Response MUST be a valid JSON object matching this schema. No formatting other than raw JSON.
        """

        res = None
        if cls._initialize_api():
            try:
                # Use standard Gemini Flash model
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                parsed = cls._parse_ai_json(response.text)
                if parsed:
                    res = parsed
            except Exception as e:
                print(f"[AI API ERROR] Failed to fetch coaching from Gemini API ({e}). Falling back.")

        if not res:
            # Fallback Mock Coach Generator
            res = cls._get_mock_coaching(emissions, scores, inputs)

        cls._insights_cache[key] = (now, res)
        return res

    @classmethod
    def predict_future_footprint(cls, user_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Predicts 30-day and 90-day footprint paths using user history.
        """
        if not user_history:
            return {
                "projection_30_days": 0.0,
                "projection_90_days": 0.0,
                "reasoning": "No history available to analyze future carbon trends."
            }

        # Structure history list
        hist_summary = []
        for h in user_history[:5]:
            hist_summary.append({
                "date": h.get("created_at", "")[:10],
                "total": h.get("emissions", {}).get("total", 0.0),
                "score": h.get("eco_score", 50.0)
            })

        latest_total = hist_summary[0]["total"]

        prompt = f"""
        You are a carbon footprint predictive forecaster. Based on the user's historical footprint changes, predict their carbon emissions path in 30 days and 90 days.
        Here is their history (newest first):
        {json.dumps(hist_summary, indent=2)}

        Generate a JSON object with:
        1. "projection_30_days": Predicted total emissions (kg CO2e) for next month.
        2. "projection_90_days": Predicted total emissions (kg CO2e) for 3 months from now.
        3. "reasoning": A 2-sentence explanation of the projection, highlighting if their footprint is expanding, shrinking, or steady and why.

        Response MUST be raw JSON matching this format.
        """

        if cls._initialize_api():
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                parsed = cls._parse_ai_json(response.text)
                if parsed:
                    return parsed
            except Exception as e:
                print(f"[AI API ERROR] Failed to fetch projection from Gemini API ({e}). Falling back.")

        # Math fallback if offline
        trend = 0.0
        if len(hist_summary) > 1:
            # Simple slope estimate
            trend = (hist_summary[0]["total"] - hist_summary[-1]["total"]) / len(hist_summary)
            
        proj_30 = max(0.0, latest_total + trend)
        proj_90 = max(0.0, latest_total + (trend * 3.0))

        direction = "shrinking" if trend < 0 else "expanding" if trend > 0 else "remaining stable"
        return {
            "projection_30_days": round(proj_30, 2),
            "projection_90_days": round(proj_90, 2),
            "reasoning": f"Based on your recent logs, your emissions are {direction}. Shifting habits will help lock in long-term savings."
        }

    @classmethod
    def generate_action_plan(cls, user_id: str, footprint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a prioritized daily, weekly, monthly smart action plan.
        """
        key = cls._make_cache_key(user_id, footprint)
        now = time.time()
        if key in cls._action_plan_cache:
            t, cached_val = cls._action_plan_cache[key]
            if now - t < cls._CACHE_TTL:
                print(f"[AI CACHE] Cache hit for user action plan: {user_id}")
                return cached_val

        emissions = footprint.get("emissions", {})
        scores = footprint.get("category_scores", {})
        
        prompt = f"""
        You are an AI Smart Action Planner for CarbonWise AI.
        Create a customized action plan for a user with these monthly emission values (kg CO2e):
        - Transport: {emissions.get('transport', 0)}
        - Energy: {emissions.get('energy', 0)}
        - Food: {emissions.get('food', 0)}
        - Consumption: {emissions.get('consumption', 0)}

        Categorize plans into three groups:
        - "daily": 2 small habits.
        - "weekly": 2 medium lifestyle efforts.
        - "monthly": 2 larger structural changes.

        For each action, supply:
        - "task": specific action title
        - "impact": "High" (heavy savings), "Medium", or "Low" (light savings)
        - "difficulty": "Easy", "Medium", "Hard"
        - "cost": "Free", "Low", "Moderate", "High"
        - "category": Which category it improves ("transport", "energy", "food", "consumption")

        Response MUST be raw JSON matching this structure.
        """

        res = None
        if cls._initialize_api():
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                parsed = cls._parse_ai_json(response.text)
                if parsed:
                    res = parsed
            except Exception as e:
                print(f"[AI API ERROR] Failed to fetch Action Plan from Gemini API ({e}). Falling back.")

        if not res:
            # Local plan generator
            res = cls._get_mock_action_plan(emissions)

        cls._action_plan_cache[key] = (now, res)
        return res

    @classmethod
    def _get_mock_coaching(cls, emissions: Dict[str, float], scores: Dict[str, float], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Creates detailed data-driven insights with explainability fields if Gemini is unavailable."""
        insights = []
        suggestions = []
        
        # Analyze transport
        gas_car = inputs.get("transport", {}).get("gas_car_km", 0.0)
        flight = inputs.get("transport", {}).get("flight_km", 0.0)
        grid_pwr = inputs.get("energy", {}).get("grid_kwh", 0.0)
        diet = inputs.get("food", {}).get("diet", "balanced")
        
        if gas_car > 300:
            insights.append("Your gasoline car commuting accounts for a significant portion of your transit emissions.")
            suggestions.append("Consider grouping errands or carpooling to reduce monthly gas car miles by 20%.")
        else:
            insights.append("Your commuting footprint is relatively light, showing effective transit optimization.")
            suggestions.append("Check if walking or cycling is viable for short trips under 2 km.")

        if grid_pwr > 200:
            insights.append("Grid-sourced electrical power represents a core decarbonization opportunity in your profile.")
            suggestions.append("Investigate local community solar options or smart plug monitors to curb phantom electricity load.")
        else:
            insights.append("Your domestic electricity consumption is efficiently maintained.")
            suggestions.append("Try installing LED bulbs throughout your workspace to squeeze out further energy efficiencies.")

        if diet == "meat_heavy":
            insights.append("A meat-heavy diet multiplies your dietary carbon footprint by up to 7 times compared to plant alternatives.")
            suggestions.append("Implement a 'Meatless Mondays' routine to transition some meals to vegetarian or vegan recipes.")
        else:
            insights.append("Your plant-inclined diet significantly curbs food-related carbon emissions.")
            suggestions.append("Prioritize buying locally grown, seasonal foods to reduce transit-mile food footprints.")

        # Make sure we have exactly 3 insights/suggestions
        insights = insights[:3]
        suggestions = suggestions[:3]
        
        # Fill placeholders if too short
        while len(insights) < 3:
            insights.append("Your consumption profile indicates balanced shopping practices.")
        while len(suggestions) < 3:
            suggestions.append("Repurpose or recycle older materials to close consumption waste loops.")

        suggestions_objects = []
        for sug in suggestions:
            why = "Chosen because this category represents a significant portion of your footprint."
            impact = "15-30 kg CO2e saved/mo"
            outcome = "Decreased utility costs and lower household resource consumption."
            
            if "miles" in sug or "errands" in sug or "commute" in sug or "cycling" in sug:
                why = "Chosen to reduce petroleum consumption in your daily commutes."
                impact = "40-80 kg CO2e saved/mo"
                outcome = "Reduced fuel expenses and lowered transportation carbon load."
            elif "solar" in sug or "LED" in sug or "plug" in sug:
                why = "Chosen to transition domestic grid loads to renewable sources."
                impact = "30-50 kg CO2e saved/mo"
                outcome = "Reduced energy bills and cleaner home power footprint."
            elif "diet" in sug or "meat-free" in sug or "vegan" in sug or "Mondays" in sug or "seasonal" in sug:
                why = "Chosen to substitute high-carbon beef meals with plant proteins."
                impact = "20-40 kg CO2e saved/mo"
                outcome = "Better personal health and lower dietary resource usage."
            
            suggestions_objects.append({
                "text": sug,
                "why_chosen": why,
                "estimated_impact": impact,
                "expected_outcome": outcome
            })

        return {
            "insights": insights,
            "suggestions": suggestions_objects,
            "weekly_goals": [
                {
                    "title": "Clean Energy Switch",
                    "description": "Switch to renewable grid tariffs or shut off appliances completely when not in use.",
                    "impact": "Medium",
                    "points": 15
                },
                {
                    "title": "Low Emission Travel",
                    "description": "Replace one gas-car commute with public transit, bicycling, or carpooling this week.",
                    "impact": "High",
                    "points": 25
                },
                {
                    "title": "Plant-Forward Day",
                    "description": "Prepare fully meat-free plant meals for an entire day to reduce resource footprint.",
                    "impact": "Medium",
                    "points": 20
                }
            ]
        }

    @classmethod
    def _get_mock_action_plan(cls, emissions: Dict[str, float]) -> Dict[str, Any]:
        """Creates structured fallback actions list."""
        return {
            "daily": [
                {
                    "task": "Unplug standby devices and electronics at night",
                    "impact": "Low",
                    "difficulty": "Easy",
                    "cost": "Free",
                    "category": "energy"
                },
                {
                    "task": "Walk or bike for short trips under 2 kilometers",
                    "impact": "Medium",
                    "difficulty": "Easy",
                    "cost": "Free",
                    "category": "transport"
                }
            ],
            "weekly": [
                {
                    "task": "Commit to 3 fully plant-based meatless days",
                    "impact": "High",
                    "difficulty": "Medium",
                    "cost": "Free",
                    "category": "food"
                },
                {
                    "task": "Consolidate grocery trips to reduce car mileage",
                    "impact": "Medium",
                    "difficulty": "Easy",
                    "cost": "Free",
                    "category": "transport"
                }
            ],
            "monthly": [
                {
                    "task": "Schedule energy audit and switch to LED bulbs",
                    "impact": "High",
                    "difficulty": "Easy",
                    "cost": "Low",
                    "category": "energy"
                },
                {
                    "task": "Purchase clothing from secondhand or thrift shops only",
                    "impact": "Medium",
                    "difficulty": "Medium",
                    "cost": "Low",
                    "category": "consumption"
                }
            ]
        }
