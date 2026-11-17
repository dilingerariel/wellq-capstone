"""Closed tenant facade. Unsupported raw operations are intentionally inaccessible."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
session_context = ContextVar("mongo_session", default=None)
COLLECTIONS = frozenset({"clinical_tests", "clinical_test_extractions", "clinical_markers", "marker_catalog",
                         "score_snapshots", "patient_access", "lab_report_exports", "audit_events", "audit_logs",
                         "request_limits", "clinical_result_history", "demo_objects"})

class TenantCollection:
    def __init__(self, collection, client_id):
        self._collection, self.client_id = collection, client_id

    def query(self, query=None):
        return {"$and": [{"client_id": self.client_id}, deepcopy(query or {})]}

    def options(self, kwargs):
        if session_context.get() is not None:
            kwargs["session"] = session_context.get()
        return kwargs

    def document(self, document):
        doc = deepcopy(document)
        if "client_id" in doc and doc["client_id"] != self.client_id:
            raise ValueError("Cross-tenant write denied")
        doc["client_id"] = self.client_id
        return doc

    @contextmanager
    def source_write(self):
        from app.services.report_version import SOURCE_COLLECTIONS, SOURCE_KEY
        if self._collection.name not in SOURCE_COLLECTIONS:
            yield
            return
        # Standalone facade writes are transactional too; nested writes reuse
        # the caller's session. Raw worker leases only change job bookkeeping.
        db = TenantDatabase(self._collection.database, self.client_id)
        with db.atomic():
            db.request_limits.update_one({"key": SOURCE_KEY}, {"$inc": {"revision": 1}}, upsert=True)
            db.lab_report_exports.update_many({"state": {"$in": ["pending", "committed"]}},
                                              {"$set": {"state": "stale"}})
            yield

    def find(self, query=None, *args, **kwargs):
        return self._collection.find(self.query(query), *args, **self.options(kwargs))

    def find_one(self, query=None, *args, **kwargs):
        return self._collection.find_one(self.query(query), *args, **self.options(kwargs))

    def count_documents(self, query, **kwargs):
        return self._collection.count_documents(self.query(query), **self.options(kwargs))

    def distinct(self, key, query=None, **kwargs):
        return self._collection.distinct(key, self.query(query), **self.options(kwargs))

    def insert_one(self, document, **kwargs):
        with self.source_write():
            return self._collection.insert_one(self.document(document), **self.options(kwargs))

    def insert_many(self, documents, **kwargs):
        with self.source_write():
            return self._collection.insert_many([self.document(d) for d in documents], **self.options(kwargs))

    def update(self, update):
        if self._collection.name in {"score_snapshots", "clinical_result_history", "audit_events", "audit_logs"}:
            raise ValueError("Append-only collection")
        if not update or any(not k.startswith("$") for k in update):
            raise ValueError("Replacement updates denied")
        for op, values in update.items():
            if op not in {"$set", "$unset", "$inc", "$setOnInsert", "$push", "$addToSet", "$pull"}:
                raise ValueError("Update operator denied")
            if any(k == "client_id" or k.startswith("client_id.") for k in values):
                raise ValueError("Tenant is immutable")
        return update

    def update_one(self, query, update, **kwargs):
        update = deepcopy(self.update(update))
        if kwargs.get("upsert"):
            if any(k.startswith("$") or k == "client_id" or isinstance(v, dict) for k, v in query.items()):
                raise ValueError("Upsert requires tenant-free equality keys")
            update.setdefault("$setOnInsert", {})["client_id"] = self.client_id
            scoped = {**deepcopy(query), "client_id": self.client_id}
        else:
            scoped = self.query(query)
        with self.source_write():
            return self._collection.update_one(scoped, update, **self.options(kwargs))

    def update_many(self, query, update, **kwargs):
        if kwargs.get("upsert"):
            raise ValueError("Bulk upsert denied")
        update = self.update(update)
        with self.source_write():
            return self._collection.update_many(self.query(query), update, **self.options(kwargs))

    def find_one_and_update(self, query, update, **kwargs):
        update = self.update(update)
        with self.source_write():
            return self._collection.find_one_and_update(self.query(query), update, **self.options(kwargs))

class TenantDatabase:
    def __init__(self, database, client_id):
        if not isinstance(client_id, str) or not client_id:
            raise ValueError("Trusted tenant required")
        self._database, self.client_id = database, client_id

    def __getitem__(self, name):
        if name not in COLLECTIONS:
            raise ValueError("Collection denied")
        return TenantCollection(self._database[name], self.client_id)

    def __getattr__(self, name):
        if name in COLLECTIONS:
            return self[name]
        raise AttributeError(name)

    @contextmanager
    def atomic(self):
        if session_context.get() is not None:
            yield
            return
        from pymongo.read_concern import ReadConcern
        from pymongo.write_concern import WriteConcern
        with self._database.client.start_session() as session:
            with session.start_transaction(read_concern=ReadConcern("snapshot"),
                                           write_concern=WriteConcern("majority")):
                token = session_context.set(session)
                try:
                    yield
                finally:
                    session_context.reset(token)
