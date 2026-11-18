"""GCS only: unavailable credentials/signatures never activate simulation."""
import hashlib
import os
import jwt
import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.config import settings

def unavailable():
    return HTTPException(503, detail={"code": "STORAGE_UNAVAILABLE", "message": "Private storage unavailable"})

class StorageService:
    def __init__(self):
        self.client = self.bucket = None

    def _bucket(self):
        if self.bucket is not None:
            return self.bucket
        if not settings.GCS_PROJECT_ID or not settings.GCS_BUCKET_NAME:
            raise unavailable()

    def _demo_storage(self):
        enabled = (settings.DEMO_MONGO_STORAGE_ENABLED and settings.DEMO_AUTH_ENABLED
                   and settings.ENVIRONMENT != "production")
        if not enabled:
            return False
        from app.database import mongodb
        if mongodb.db is None:
            raise unavailable()
        return True

    @staticmethod
    def _demo_token(purpose, object_key, client_id, minutes, **claims):
        from app.routes.demo import get_demo_private_key
        from app.config import settings
        now = datetime.utcnow()
        ttl = timedelta(minutes=minutes)
        return jwt.encode({"purpose": purpose, "object_key": object_key, "client_id": client_id,
                           "iat": now, "nbf": now, "exp": now + ttl,
                           "iss": settings.JWT_ISSUER, "aud": settings.JWT_AUDIENCE,
                           "jti": uuid.uuid4().hex, **claims},
                          get_demo_private_key(), algorithm="RS256")

    @staticmethod
    def _demo_base_url():
        configured = settings.DEMO_PUBLIC_API_BASE_URL
        if configured:
            return configured.rstrip("/")
        host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
        if host:
            return "https://" + host.removeprefix("https://").rstrip("/")
        return ""
        try:
            from google.cloud import storage
            self.client = (storage.Client.from_service_account_json(settings.GCS_CREDENTIALS_PATH)
                           if settings.GCS_CREDENTIALS_PATH else storage.Client(project=settings.GCS_PROJECT_ID))
            bucket = self.client.bucket(settings.GCS_BUCKET_NAME)
            bucket.reload(timeout=15)
            if not bucket.iam_configuration.uniform_bucket_level_access_enabled or bucket.iam_configuration.public_access_prevention != "enforced":
                raise ValueError("Private bucket controls required")
            self.bucket = bucket
            return bucket
        except Exception:
            raise unavailable()

    def generate_upload_url(self, object_key, content_type, expiration_minutes=15,
                            client_id=None, patient_id=None, size_bytes=None, sha256=None):
        if not object_key.startswith("quarantine/clinical-tests/"):
            raise ValueError("Quarantine upload required")
        ttl = min(expiration_minutes, settings.SIGNED_URL_EXPIRATION_MINUTES)
        if self._demo_storage():
            if (client_id != "clinica_alemana" or content_type != "application/pdf"
                    or sha256 != "3331e1f6f50397609563dacbdf46d5c6f41d3d530c9f8e3697d136915c4907a6"
                    or size_bytes != 2485):
                raise HTTPException(422, detail={"code": "SYNTHETIC_FILE_REQUIRED", "message": "Only the fixed synthetic PDF is accepted"})
            if not isinstance(patient_id, str) or not patient_id:
                raise HTTPException(403, detail={"code": "PATIENT_REQUIRED", "message": "Patient identity required"})
            token = self._demo_token("demo_upload", object_key, client_id, ttl, patient_id=patient_id,
                                     expected_size=size_bytes, expected_sha256=sha256)
            url = self._demo_base_url() + "/api/v1/demo/storage/upload"
            return {"method": "PUT", "signed_url": url,
                    "required_headers": {"Content-Type": content_type, "x-wellq-upload-token": token,
                                         "x-wellq-if-absent": "true"},
                    "expires_at": (datetime.utcnow() + timedelta(minutes=ttl)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        headers = {"x-goog-if-generation-match": "0"}
        try:
            url = self._bucket().blob(object_key).generate_signed_url(version="v4", expiration=timedelta(minutes=ttl),
                method="PUT", content_type=content_type, headers=headers)
            return {"method": "PUT", "signed_url": url, "required_headers": {"Content-Type": content_type, **headers},
                    "expires_at": (datetime.utcnow() + timedelta(minutes=ttl)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        except Exception:
            raise unavailable()

    def generate_download_url(self, object_key, expiration_minutes=5, generation=None):
        if not object_key.startswith("private/"):
            raise ValueError("Unvalidated download denied")
        ttl = min(expiration_minutes, settings.DOWNLOAD_URL_EXPIRATION_MINUTES)
        if self._demo_storage():
            from app.database import mongodb
            stored = mongodb.db.demo_objects.find_one({"client_id": "clinica_alemana", "object_key": object_key})
            if not stored or (generation is not None and stored.get("generation") != generation):
                raise unavailable()
            token = self._demo_token("demo_download", object_key, "clinica_alemana", ttl,
                                     generation=stored["generation"])
            url = self._demo_base_url() + "/api/v1/demo/storage/download?token=" + token
            return {"url": url, "expires_at": (datetime.utcnow() + timedelta(minutes=ttl)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        try:
            url = self._bucket().blob(object_key, generation=generation).generate_signed_url(version="v4",
                expiration=timedelta(minutes=ttl), method="GET", generation=generation)
            return {"url": url, "expires_at": (datetime.utcnow() + timedelta(minutes=ttl)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        except Exception:
            raise unavailable()

    def read_object(self, object_key, generation=None):
        if self._demo_storage():
            from app.database import mongodb
            stored = mongodb.db.demo_objects.find_one({"client_id": "clinica_alemana", "object_key": object_key})
            if not stored or (generation is not None and stored.get("generation") != generation):
                raise unavailable()
            data = bytes(stored["data"])
            if len(data) > settings.MAX_CLINICAL_FILE_BYTES:
                from app.services.file_validation import FileRejected
                raise FileRejected("SIZE_REJECTED")
            return data, stored["content_type"], int(stored["generation"])
        try:
            blob = self._bucket().blob(object_key, generation=generation)
            blob.reload(timeout=15)
            if not blob.size or blob.size > settings.MAX_CLINICAL_FILE_BYTES:
                from app.services.file_validation import FileRejected
                raise FileRejected("SIZE_REJECTED")
            data = blob.download_as_bytes(if_generation_match=blob.generation, timeout=30)
            if len(data) != blob.size:
                raise ValueError("Truncated object")
            return data, blob.content_type, int(blob.generation)
        except ValueError:
            raise
        except Exception:
            raise unavailable()

    def promote(self, object_key, generation, sha256):
        if self._demo_storage():
            from app.database import mongodb
            stored = mongodb.db.demo_objects.find_one({"client_id": "clinica_alemana", "object_key": object_key,
                                                       "generation": generation, "sha256": sha256})
            if not stored:
                raise unavailable()
            destination = object_key.replace("quarantine/", "private/", 1) + "/" + sha256
            result = mongodb.db.demo_objects.update_one({"client_id": "clinica_alemana", "object_key": object_key,
                "generation": generation, "sha256": sha256}, {"$set": {"object_key": destination}})
            if result.modified_count != 1:
                existing = mongodb.db.demo_objects.find_one({"client_id": "clinica_alemana", "object_key": destination,
                    "generation": generation, "sha256": sha256})
                if not existing:
                    raise ValueError("Promotion conflict")
            return destination, int(generation)
        from google.api_core.exceptions import PreconditionFailed
        destination = object_key.replace("quarantine/", "private/", 1) + "/" + sha256
        try:
            bucket = self._bucket()
            try:
                copied = bucket.copy_blob(bucket.blob(object_key, generation=generation), bucket, new_name=destination,
                    if_generation_match=0, if_source_generation_match=generation, timeout=30)
                return destination, int(copied.generation)
            except PreconditionFailed:
                data, _, existing = self.read_object(destination)
                if hashlib.sha256(data).hexdigest() != sha256:
                    raise ValueError("Promotion conflict")
                return destination, existing
        except Exception:
            raise unavailable()

    def upload_bytes(self, object_key, data, content_type="application/pdf"):
        if not object_key.startswith("private/lab-reports/"):
            raise ValueError("Private report prefix required")
        try:
            self._bucket().blob(object_key).upload_from_string(data, content_type=content_type, if_generation_match=0, timeout=30)
            return "gcs"
        except Exception:
            raise unavailable()

    def verify_object_exists(self, object_key):
        try:
            return self._bucket().blob(object_key).exists(timeout=15)
        except Exception:
            raise unavailable()

storage_service = StorageService()
