"""
Centralized Configuration Module for CarbonWise AI.
Responsible for loading environment variables and validating setup parameters.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration settings."""
    
    # Flask Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-insecure-dev-key-carbonwise-ai")
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = FLASK_ENV == "development"
    
    # Server Settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", 5000))
    
    # MongoDB Config
    MONGO_URI: Optional[str] = os.getenv("MONGO_URI")
    
    # AI Engine Config
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    
    # Fallback/Mock Mode flags for testing and local evaluation
    MOCK_MODE: bool = False
    
    @classmethod
    def validate_and_log(cls) -> None:
        """
        Validates the configuration at start and flags if mock mode should be activated
        due to missing API keys or DB configurations.
        """
        if not cls.GEMINI_API_KEY or cls.GEMINI_API_KEY.strip() == "":
            print("[WARNING] GEMINI_API_KEY is not configured. CarbonWise AI will run in Mock AI Mode.")
            cls.MOCK_MODE = True
        
        if not cls.MONGO_URI or cls.MONGO_URI.strip() == "":
            print("[WARNING] MONGO_URI is not configured. Falling back to local Mock Database Mode.")
            cls.MONGO_URI = "mongodb://localhost:27017/carbonwise"
            cls.MOCK_MODE = True
