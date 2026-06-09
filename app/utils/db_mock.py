"""
Mock Database Engine for CarbonWise AI.

Provides a lightweight, thread-safe, file-backed in-process document store
that mimics the PyMongo collection API. This module is used in two scenarios:

1. **Local development** — when ``MONGO_URI`` is not configured, the app runs
   entirely on the local JSON file without requiring a live database server.
2. **Testing** — the test suite injects a ``JSONDatabaseMock`` instance pointed
   at a temporary file path to keep tests isolated and deterministic.

The public interface deliberately mirrors PyMongo's ``Collection`` API so that
service-layer code works unchanged against both backends.

Architecture role: Infrastructure / test-double layer. Imported by ``app.db``
which decides at runtime which backend to serve to the application.

Typical usage:
    from app.utils.db_mock import JSONDatabaseMock
    db = JSONDatabaseMock(filepath="test_db.json")
    db["users"].insert_one({"username": "alice"})
    user = db["users"].find_one({"username": "alice"})
"""

import json
import os
import threading
from typing import Any, Dict, List, Optional

# Default collection names initialised in a fresh database file
_DEFAULT_COLLECTIONS: Dict[str, List] = {
    "users": [],
    "calculations": [],
    "goals": [],
    "analytics": [],
}


class JSONDatabaseMock:
    """File-backed in-process document store with a PyMongo-compatible API.

    Persists data as a JSON array per collection inside a single flat file.
    All read/write operations are protected by a threading.Lock to make the
    store safe for concurrent use within a single process.

    Attributes:
        filepath: Absolute or relative path to the backing JSON file.
    """

    def __init__(self, filepath: str = "local_db.json") -> None:
        """Initialise the mock store and create the backing file if absent.

        Args:
            filepath: Path to the JSON file used for persistence. Defaults to
                ``"local_db.json"`` in the current working directory.
        """
        self.filepath = filepath
        self._lock = threading.Lock()
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as fh:
                json.dump(_DEFAULT_COLLECTIONS, fh)

    def _read(self) -> Dict[str, List[Dict[str, Any]]]:
        """Read and deserialise the entire database file.

        Returns:
            Dict[str, List[Dict[str, Any]]]: Mapping of collection name to
            list of documents. Returns an empty default structure on any I/O
            or JSON decode error to prevent cascading failures.
        """
        with self._lock:
            try:
                with open(self.filepath, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                return dict(_DEFAULT_COLLECTIONS)

    def _write(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Serialise and persist the entire database back to disk.

        Args:
            data: Full database mapping to write. All existing content is
                replaced atomically (within the same lock as the calling
                operation).
        """
        with self._lock:
            with open(self.filepath, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)

    class MockCollection:
        """PyMongo Collection interface backed by a JSON array.

        Supports the subset of the PyMongo ``Collection`` API used by
        CarbonWise AI service-layer code: ``insert_one``, ``find_one``,
        ``find``, ``update_one``, ``delete_one``, and ``count_documents``.

        Attributes:
            parent: The owning ``JSONDatabaseMock`` instance used to read
                and write the backing file.
            name: Collection name — maps to a top-level key in the JSON file.
        """

        def __init__(self, parent: "JSONDatabaseMock", name: str) -> None:
            """Bind the collection to its parent store.

            Args:
                parent: Owning ``JSONDatabaseMock`` instance.
                name: Collection name used as the JSON file key.
            """
            self.parent = parent
            self.name = name

        def insert_one(self, document: Dict[str, Any]) -> Any:
            """Insert a single document, auto-generating ``_id`` if absent.

            Args:
                document: Dictionary to insert. Modified in-place to add
                    ``_id`` if the key is not already present.

            Returns:
                Any: A result object with an ``inserted_id`` attribute
                mirroring PyMongo's ``InsertOneResult``.
            """
            data = self.parent._read()
            if self.name not in data:
                data[self.name] = []

            # Auto-generate a sequential string ID when the caller omits one
            if "_id" not in document:
                document["_id"] = str(len(data[self.name]) + 1)

            data[self.name].append(document)
            self.parent._write(data)

            class InsertResult:
                inserted_id = document["_id"]

            return InsertResult()

        def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Return the first document matching all query fields.

            Args:
                query: Equality filter as a flat ``{field: value}`` mapping.

            Returns:
                Optional[Dict[str, Any]]: The first matching document, or
                ``None`` when no document satisfies the query.
            """
            data = self.parent._read()
            for doc in data.get(self.name, []):
                if self._matches(doc, query):
                    return doc
            return None

        def find(self, query: Optional[Dict[str, Any]] = None) -> "MockCollection.Cursor":
            """Return all documents matching the query.

            Args:
                query: Equality filter. Defaults to ``{}`` which matches every
                    document in the collection.

            Returns:
                Cursor: A list subclass that additionally exposes ``sort()``
                and ``limit()`` methods to mirror PyMongo's cursor API.
            """
            query = query or {}
            data = self.parent._read()
            results = [
                doc for doc in data.get(self.name, [])
                if self._matches(doc, query)
            ]

            class Cursor(list):
                """Minimal PyMongo cursor replacement."""

                def sort(self, key_name: str, direction: int = -1) -> "Cursor":
                    """Sort results in-place by a document field.

                    Args:
                        key_name: Field name to sort by.
                        direction: ``-1`` for descending (default), ``1`` for
                            ascending — matches PyMongo's sort direction constants.

                    Returns:
                        Cursor: ``self`` after sorting, enabling method chaining.
                    """
                    reverse = direction == -1
                    # Use empty string as sentinel for missing keys so sorting
                    # does not raise TypeError on heterogeneous documents.
                    super().sort(
                        key=lambda doc: doc.get(key_name, ""), reverse=reverse
                    )
                    return self

                def limit(self, count: int) -> "Cursor":
                    """Truncate the cursor to at most ``count`` documents.

                    Args:
                        count: Maximum number of documents to return.

                    Returns:
                        Cursor: New cursor containing at most ``count`` items.
                    """
                    return Cursor(self[:count])

            return Cursor(results)

        def update_one(
            self,
            query: Dict[str, Any],
            update: Dict[str, Any],
            upsert: bool = False,
        ) -> Any:
            """Update the first document matching ``query``.

            Supports the ``$set`` update operator. When ``$set`` is absent the
            entire document is replaced. When ``upsert=True`` and no document
            matches, a new document is inserted by merging ``query`` fields
            with the update payload.

            Args:
                query: Equality filter identifying the target document.
                update: Update specification. Use ``{"$set": {...}}`` to
                    patch individual fields, or a plain dict to replace.
                upsert: When ``True``, insert a new document if no match is
                    found. Defaults to ``False``.

            Returns:
                Any: A result object with ``matched_count`` and
                ``modified_count`` attributes mirroring PyMongo's
                ``UpdateResult``.
            """
            data = self.parent._read()
            collection = data.get(self.name, [])
            found = False

            for i, doc in enumerate(collection):
                if self._matches(doc, query):
                    found = True
                    # Apply $set patch or full document replacement
                    if "$set" in update:
                        for key, val in update["$set"].items():
                            collection[i][key] = val
                    elif "$push" in update:
                        # Support $push operator for appending to array fields
                        for key, val in update["$push"].items():
                            collection[i].setdefault(key, []).append(val)
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
            """Delete the first document matching ``query``.

            Args:
                query: Equality filter identifying the document to remove.

            Returns:
                Any: A result object with a ``deleted_count`` attribute
                mirroring PyMongo's ``DeleteResult``.
            """
            data = self.parent._read()
            collection = data.get(self.name, [])
            original_len = len(collection)
            # Rebuild the collection excluding the first matched document
            removed = False
            new_collection = []
            for doc in collection:
                if not removed and self._matches(doc, query):
                    removed = True
                else:
                    new_collection.append(doc)
            data[self.name] = new_collection
            self.parent._write(data)

            class DeleteResult:
                deleted_count = original_len - len(new_collection)

            return DeleteResult()

        def count_documents(self, query: Dict[str, Any]) -> int:
            """Count documents matching ``query``.

            Args:
                query: Equality filter. Pass ``{}`` to count every document.

            Returns:
                int: Number of documents that satisfy the query.
            """
            return len(self.find(query))

        def _matches(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
            """Check whether ``doc`` satisfies all equality conditions in ``query``.

            Performs shallow equality checks on each key-value pair in the
            query. Only top-level field equality is supported — no nested
            operators or dot-notation paths.

            Args:
                doc: Document to evaluate.
                query: Flat equality filter mapping field names to expected values.

            Returns:
                bool: ``True`` when every query field matches the document value,
                ``False`` if any field is absent or has a different value.
            """
            for key, value in query.items():
                if key not in doc or doc[key] != value:
                    return False
            return True

    def __getitem__(self, collection_name: str) -> "JSONDatabaseMock.MockCollection":
        """Return a ``MockCollection`` handle for the named collection.

        Args:
            collection_name: Name of the collection to access.

        Returns:
            MockCollection: Collection interface for the requested name.
        """
        return self.MockCollection(self, collection_name)
