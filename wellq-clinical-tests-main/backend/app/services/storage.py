"""GCS only: unavailable credentials/signatures never activate simulation."""
import hashlib
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

    def generate_upload_url(self, object_key, content_type, expiration_minutes=15):
        if not object_key.startswith("quarantine/clinical-tests/"):
            raise ValueError("Quarantine upload required")
        ttl = min(expiration_minutes, settings.SIGNED_URL_EXPIRATION_MINUTES)
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
        try:
            url = self._bucket().blob(object_key, generation=generation).generate_signed_url(version="v4",
                expiration=timedelta(minutes=ttl), method="GET", generation=generation)
            return {"url": url, "expires_at": (datetime.utcnow() + timedelta(minutes=ttl)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        except Exception:
            raise unavailable()

    def read_object(self, object_key, generation=None):
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
