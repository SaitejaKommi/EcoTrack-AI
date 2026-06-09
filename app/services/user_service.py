"""
User Service for CarbonWise AI.

Manages all user-account operations: creating accounts, validating credentials,
retrieving profile data, updating daily activity streaks, and awarding
gamification badges.

Password storage uses ``werkzeug.security`` PBKDF2-SHA256 hashing — passwords
are never stored in plain text. The streak algorithm resets the counter when
more than one day has elapsed since the last interaction, and promotes the
counter when interactions occur on consecutive days.

Architecture role: Business logic / service layer — mediates between the
authentication route handlers and the database. Contains no Flask-specific
imports so it can be unit-tested without an application context.

Typical usage:
    from app.services.user_service import UserService
    success, user_id = UserService.create_user(validated_data)
    user_info = UserService.authenticate_user(credentials)
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from werkzeug.security import check_password_hash, generate_password_hash

from app.constants import BADGE_CONFIGS, STREAK_BUILDER_BADGE_THRESHOLD
from app.db import get_db

logger = logging.getLogger(__name__)


class UserService:
    """Service class for user profile management and gamification mechanics.

    All methods are ``@staticmethod`` — no instance state is maintained.
    """

    @staticmethod
    def create_user(user_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Register a new user account in the database.

        Checks for duplicate emails before inserting to enforce uniqueness
        without relying on database-level unique indexes (which may not be
        available on the JSON mock backend).

        Args:
            user_data: Sanitised registration payload containing:
                - ``"username"``: Display name string.
                - ``"email"``: Lowercase email address.
                - ``"password"``: Plain-text password to be hashed.

        Returns:
            Tuple[bool, str]:
                - ``True`` and the new user's string ID on success.
                - ``False`` and a human-readable error message on failure.

        Raises:
            No exceptions — database errors propagate as-is to the caller.
        """
        db = get_db()
        email = user_data["email"].lower()

        # Reject duplicate registrations before hashing to save computation
        if db["users"].find_one({"email": email}):
            return False, "A user with this email address already exists."

        hashed_password = generate_password_hash(user_data["password"])

        new_user: Dict[str, Any] = {
            "username": user_data["username"],
            "email": email,
            "password_hash": hashed_password,
            "created_at": datetime.utcnow().isoformat(),
            "badges": [],           # Earned badge documents appended on award
            "streak": 0,            # Consecutive-day interaction count
            "last_active_date": None,  # ISO date string "YYYY-MM-DD"
        }

        result = db["users"].insert_one(new_user)
        return True, str(result.inserted_id)

    @staticmethod
    def authenticate_user(
        credentials: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate login credentials and return sanitised user data on success.

        Verifies the supplied password against the stored PBKDF2 hash.
        Sensitive fields (``password_hash``) are stripped from the returned
        document before it reaches the route handler.

        Args:
            credentials: Login payload containing ``"email"`` and ``"password"``.

        Returns:
            Optional[Dict[str, Any]]: Sanitised user document on success, or
            ``None`` when the email is unknown or the password does not match.

        Raises:
            No exceptions — authentication failures return ``None``.
        """
        db = get_db()
        email = credentials["email"].lower()
        user = db["users"].find_one({"email": email})

        if not user:
            return None

        if not check_password_hash(user["password_hash"], credentials["password"]):
            return None

        # Return only safe fields — never expose the password hash
        return {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"],
            "streak": user.get("streak", 0),
            "badges": user.get("badges", []),
            "last_active_date": user.get("last_active_date"),
        }

    @staticmethod
    def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the public profile document for a user.

        Attempts lookup by ``_id`` first, then falls back to the string
        ``"id"`` field which the JSON mock backend uses instead of ObjectId.

        Args:
            user_id: The user's string identifier as stored in the session.

        Returns:
            Optional[Dict[str, Any]]: Sanitised profile dict on success, or
            ``None`` when no matching user is found.

        Raises:
            No exceptions — missing users return ``None``.
        """
        db = get_db()
        user = db["users"].find_one({"_id": user_id}) or db["users"].find_one({"id": user_id})

        if not user:
            return None

        return {
            "id": str(user.get("_id", user.get("id"))),
            "username": user["username"],
            "email": user["email"],
            "streak": user.get("streak", 0),
            "badges": user.get("badges", []),
            "last_active_date": user.get("last_active_date"),
            "created_at": user.get("created_at"),
        }

    @staticmethod
    def update_activity_streak(user_id: str) -> int:
        """Update the user's consecutive daily activity streak.

        Streak rules:
        - First-ever interaction → streak = 1.
        - Interaction on same calendar day as last → streak unchanged.
        - Interaction on the calendar day immediately after last → streak + 1.
        - Gap of more than one day → streak resets to 1.

        After updating the streak, proactively awards the Habit Builder badge
        when the threshold is reached.

        Args:
            user_id: Authenticated user identifier.

        Returns:
            int: Updated streak count, or ``0`` when the user is not found.

        Raises:
            No exceptions — unknown users return ``0``.
        """
        db = get_db()
        user = db["users"].find_one({"_id": user_id}) or db["users"].find_one({"id": user_id})
        if not user:
            return 0

        new_streak = _compute_new_streak(user)

        db["users"].update_one(
            {"_id": user.get("_id")},
            {"$set": {"streak": new_streak, "last_active_date": datetime.utcnow().strftime("%Y-%m-%d")}},
        )

        # Check streak milestone — award Habit Builder badge at STREAK_BUILDER_BADGE_THRESHOLD days
        if new_streak >= STREAK_BUILDER_BADGE_THRESHOLD:
            UserService.award_badge(user_id, "streak_master")

        return new_streak

    @staticmethod
    def award_badge(user_id: str, badge_id: str) -> bool:
        """Award a gamification badge to the user if they do not already hold it.

        Args:
            user_id: Authenticated user identifier.
            badge_id: Unique badge key from ``BADGE_CONFIGS`` (e.g. ``"transit_hero"``).

        Returns:
            bool: ``True`` when the badge is newly awarded, ``False`` when the
            badge ID is unknown or the user already holds the badge.

        Raises:
            No exceptions — invalid users or badge IDs return ``False``.
        """
        if badge_id not in BADGE_CONFIGS:
            return False

        db = get_db()
        user = db["users"].find_one({"_id": user_id}) or db["users"].find_one({"id": user_id})
        if not user:
            return False

        # Skip if the badge is already in the user's badge list
        if any(b["badge_id"] == badge_id for b in user.get("badges", [])):
            return False

        new_badge_entry = _build_badge_entry(badge_id)

        db["users"].update_one(
            {"_id": user.get("_id")},
            {"$push": {"badges": new_badge_entry}},
        )
        return True


# ─── Private Helper Functions ─────────────────────────────────────────────────


def _compute_new_streak(user: Dict[str, Any]) -> int:
    """Determine the updated streak count from the user document.

    Compares today's date against ``last_active_date`` to apply streak
    continuation, preservation, or reset logic.

    Args:
        user: User document from the database including ``"streak"`` and
            ``"last_active_date"`` fields.

    Returns:
        int: New streak value after applying today's interaction.
    """
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    last_active = user.get("last_active_date")
    current_streak = user.get("streak", 0)

    if last_active is None:
        # First ever interaction — initialise the streak
        return 1
    if last_active == today_str:
        # Already recorded an interaction today — preserve streak
        return current_streak
    if last_active == yesterday_str:
        # Consecutive day — extend the streak
        return current_streak + 1
    # Gap detected — reset streak to restart the chain
    return 1


def _build_badge_entry(badge_id: str) -> Dict[str, Any]:
    """Construct the badge sub-document to embed in the user's badges array.

    Args:
        badge_id: Unique badge key present in ``BADGE_CONFIGS``.

    Returns:
        Dict[str, Any]: Badge document with ``badge_id``, ``title``,
        ``description``, ``icon``, and ``awarded_at`` fields.
    """
    config = BADGE_CONFIGS[badge_id]
    return {
        "badge_id": badge_id,
        "title": config["title"],
        "description": config["description"],
        "icon": config["icon"],
        "awarded_at": datetime.utcnow().isoformat(),
    }
