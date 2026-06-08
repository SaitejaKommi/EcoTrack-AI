"""
User Service Module for CarbonWise AI.
Manages user authentication, profile operations, logins, and gamification metrics (streaks, badges).
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_db
from app.constants import BADGE_CONFIGS

class UserService:
    """Service class for user profiles, credentials, and gamification telemetry."""

    @staticmethod
    def create_user(user_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Registers a new user record.
        Args:
            user_data: Dictionary containing username, email, and password.
        Returns:
            Tuple[bool, str]: (Success status, message or user_id)
        """
        db = get_db()
        email = user_data["email"].lower()
        
        # Check if user already exists
        existing_user = db["users"].find_one({"email": email})
        if existing_user:
            return False, "A user with this email address already exists."
        
        # Encrypt password securely
        hashed_password = generate_password_hash(user_data["password"])
        
        new_user = {
            "username": user_data["username"],
            "email": email,
            "password_hash": hashed_password,
            "created_at": datetime.utcnow().isoformat(),
            "badges": [],              # List of badges awarded: [{"badge_id": "...", "awarded_at": "..."}]
            "streak": 0,               # Active login/update streak
            "last_active_date": None   # Date of last transaction (YYYY-MM-DD)
        }
        
        res = db["users"].insert_one(new_user)
        return True, str(res.inserted_id)

    @staticmethod
    def authenticate_user(credentials: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validates login credentials.
        Args:
            credentials: Dictionary with email and password.
        Returns:
            Optional[Dict[str, Any]]: Sanitized user document if valid, else None.
        """
        db = get_db()
        email = credentials["email"].lower()
        
        user = db["users"].find_one({"email": email})
        if not user:
            return None
            
        # Safe password check
        if check_password_hash(user["password_hash"], credentials["password"]):
            # Sanitize document before returning
            user_info = {
                "id": str(user["_id"]),
                "username": user["username"],
                "email": user["email"],
                "streak": user.get("streak", 0),
                "badges": user.get("badges", []),
                "last_active_date": user.get("last_active_date")
            }
            return user_info
            
        return None

    @staticmethod
    def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves user document details sanitized of password hash.
        """
        db = get_db()
        user = db["users"].find_one({"_id": user_id})
        if not user:
            # Fallback check for mock DB using string ID instead of ObjectId
            user = db["users"].find_one({"id": user_id})
            
        if user:
            return {
                "id": str(user.get("_id", user.get("id"))),
                "username": user["username"],
                "email": user["email"],
                "streak": user.get("streak", 0),
                "badges": user.get("badges", []),
                "last_active_date": user.get("last_active_date"),
                "created_at": user.get("created_at")
            }
        return None

    @staticmethod
    def update_activity_streak(user_id: str) -> int:
        """
        Updates the user's interaction streak based on daily actions.
        Returns:
            int: The updated streak count.
        """
        db = get_db()
        user = db["users"].find_one({"_id": user_id})
        if not user:
            user = db["users"].find_one({"id": user_id})
            if not user:
                return 0
                
        now = datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        
        last_active = user.get("last_active_date")
        current_streak = user.get("streak", 0)
        
        new_streak = current_streak
        
        if last_active is None:
            # First interaction ever
            new_streak = 1
        elif last_active == today_str:
            # Already updated today, keep streak the same
            pass
        elif last_active == yesterday_str:
            # Consecutive day update
            new_streak += 1
        else:
            # Streak broken
            new_streak = 1
            
        # Save streak and active timestamp
        db["users"].update_one(
            {"_id": user.get("_id")},
            {"$set": {"streak": new_streak, "last_active_date": today_str}}
        )
        
        # Proactively check streak milestone badge
        if new_streak >= 7:
            UserService.award_badge(user_id, "streak_master")
            
        return new_streak

    @staticmethod
    def award_badge(user_id: str, badge_id: str) -> bool:
        """
        Awards a badge to a user if not already unlocked.
        Args:
            user_id: User identifier.
            badge_id: Unique key of the badge in BADGE_CONFIGS.
        Returns:
            bool: True if badge was newly awarded, False if user already had it.
        """
        if badge_id not in BADGE_CONFIGS:
            return False
            
        db = get_db()
        user = db["users"].find_one({"_id": user_id})
        if not user:
            user = db["users"].find_one({"id": user_id})
            if not user:
                return False
                
        badges = user.get("badges", [])
        
        # Check if badge already awarded
        if any(b["badge_id"] == badge_id for b in badges):
            return False
            
        # Add badge
        new_badge_entry = {
            "badge_id": badge_id,
            "title": BADGE_CONFIGS[badge_id]["title"],
            "description": BADGE_CONFIGS[badge_id]["description"],
            "icon": BADGE_CONFIGS[badge_id]["icon"],
            "awarded_at": datetime.utcnow().isoformat()
        }
        
        db["users"].update_one(
            {"_id": user.get("_id")},
            {"$push": {"badges": new_badge_entry}}
        )
        return True
