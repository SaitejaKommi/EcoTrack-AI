"""
Database Management Module for CarbonWise AI.
Configures MongoDB Atlas connection or defaults to a local JSON file-based database
to ensure portability and offline functionality.
"""

import json
import os
import threading
from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
from app.config import Config

# Global database reference
_db_instance = None
_lock = threading.Lock()

from app.utils.db_mock import JSONDatabaseMock

def get_db() -> Any:
    """
    Returns database connection instance. Performs thread-safe lazy loading
    and falls back to JSONDatabaseMock if Mongo fails.
    """
    global _db_instance
    with _lock:
        if _db_instance is not None:
            return _db_instance

        # Read config URI
        mongo_uri = Config.MONGO_URI
        
        # If running in explicit mock mode or no URI is specified
        if Config.MOCK_MODE or not mongo_uri:
            print("[DB] Initializing local JSON database engine fallback...")
            _db_instance = JSONDatabaseMock()
            return _db_instance

        try:
            print(f"[DB] Attempting connection to MongoDB...")
            # Set short timeouts so connection attempts don't hang the thread indefinitely
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000, connectTimeoutMS=2000)
            # Force connection check
            client.admin.command('ping')
            # Extract database name from connection URI or default
            db_name = mongo_uri.split('/')[-1] if '/' in mongo_uri.split('//')[-1] else 'carbonwise'
            if '?' in db_name:
                db_name = db_name.split('?')[0]
            _db_instance = client[db_name]
            print(f"[DB] Successfully connected to MongoDB Database: {db_name}")
        except (ConnectionFailure, ConfigurationError, Exception) as e:
            print(f"[DB ERROR] Failed to connect to MongoDB Atlas ({e}). Activating JSON fallback...")
            _db_instance = JSONDatabaseMock()
            Config.MOCK_MODE = True
        
        return _db_instance
