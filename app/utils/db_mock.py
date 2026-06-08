"""
Mock Database Engine for CarbonWise AI.
A thread-safe, local file JSON-based persistent document store mockup.
"""

import json
import os
import threading
from typing import Dict, Any, List, Optional

class JSONDatabaseMock:
    """
    A lightweight, thread-safe, JSON-based persistent document store mockup.
    Mimics PyMongo collection API for basic operations (insert, find, update).
    """
    def __init__(self, filepath: str = "local_db.json") -> None:
        self.filepath = filepath
        self._lock = threading.Lock()
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                json.dump({"users": [], "calculations": [], "goals": [], "analytics": []}, f)

    def _read(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._lock:
            try:
                with open(self.filepath, "r") as f:
                    return json.load(f)
            except Exception:
                return {"users": [], "calculations": [], "goals": [], "analytics": []}

    def _write(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        with self._lock:
            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=2)

    class MockCollection:
        """Mock representation of a PyMongo Collection."""
        def __init__(self, parent: 'JSONDatabaseMock', name: str) -> None:
            self.parent = parent
            self.name = name

        def insert_one(self, document: Dict[str, Any]) -> Any:
            data = self.parent._read()
            if self.name not in data:
                data[self.name] = []
            
            # Generate simple ID if not present
            if "_id" not in document:
                document["_id"] = str(len(data[self.name]) + 1)
            
            data[self.name].append(document)
            self.parent._write(data)
            
            class InsertResult:
                inserted_id = document["_id"]
            return InsertResult()

        def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            data = self.parent._read()
            collection = data.get(self.name, [])
            for doc in collection:
                if self._matches(doc, query):
                    return doc
            return None

        def find(self, query: Dict[str, Any] = None) -> List[Dict[str, Any]]:
            query = query or {}
            data = self.parent._read()
            collection = data.get(self.name, [])
            results = []
            for doc in collection:
                if self._matches(doc, query):
                    results.append(doc)
            
            class Cursor(list):
                def sort(self, key_name, direction=-1):
                    # Sort results in-place
                    reverse = (direction == -1)
                    super().sort(key=lambda x: x.get(key_name, ""), reverse=reverse)
                    return self
                
                def limit(self, count):
                    return Cursor(self[:count])
            
            return Cursor(results)

        def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> Any:
            data = self.parent._read()
            collection = data.get(self.name, [])
            found = False
            
            # Find and modify
            for i, doc in enumerate(collection):
                if self._matches(doc, query):
                    found = True
                    # Process $set operator if present
                    if "$set" in update:
                        for k, v in update["$set"].items():
                            collection[i][k] = v
                    else:
                        collection[i] = update
                    break
            
            if not found and upsert:
                new_doc = query.copy()
                if "$set" in update:
                    new_doc.update(update["$set"])
                else:
                    new_doc.update(update)
                collection.append(new_doc)
            
            data[self.name] = collection
            self.parent._write(data)
            
            class UpdateResult:
                matched_count = 1 if found else 0
                modified_count = 1 if found else 0
            return UpdateResult()

        def delete_one(self, query: Dict[str, Any]) -> Any:
            data = self.parent._read()
            collection = data.get(self.name, [])
            original_len = len(collection)
            collection = [doc for doc in collection if not self._matches(doc, query)]
            data[self.name] = collection
            self.parent._write(data)
            
            class DeleteResult:
                deleted_count = original_len - len(collection)
            return DeleteResult()

        def count_documents(self, query: Dict[str, Any]) -> int:
            return len(self.find(query))

        def _matches(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
            """Evaluates query match."""
            for k, v in query.items():
                if k not in doc or doc[k] != v:
                    return False
            return True

    def __getitem__(self, collection_name: str) -> MockCollection:
        return self.MockCollection(self, collection_name)
