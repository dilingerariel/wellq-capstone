import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.bucket_name = settings.GCS_BUCKET_NAME
        self.project_id = settings.GCS_PROJECT_ID
        self.credentials_path = settings.GCS_CREDENTIALS_PATH
        self.client = None
        self.bucket = None
        self._init_client()

    def _init_client(self):
        """Inicializar cliente de GCS o modo mock si no hay credenciales"""
        try:
            if self.credentials_path and os.path.exists(self.credentials_path) and self.project_id != "your-gcp-project-id":
                from google.cloud import storage
                self.client = storage.Client.from_service_account_json(self.credentials_path)
                self.bucket = self.client.bucket(self.bucket_name)
                logger.info(f"✅ GCS Client conectado al bucket: {self.bucket_name}")
            else:
                logger.info(f"ℹ️ Modo desarrollo: GCS funcionando en modo mock (bucket={self.bucket_name}).")
        except Exception as e:
            logger.warning(f"No se pudo inicializar GCS real ({e}); usando modo mock.")
            self.client = None

    def generate_upload_url(self, object_key: str, content_type: str, expiration_minutes: int = 15) -> Dict[str, Any]:
        """Generar URL firmada V4 para subida (método PUT)"""
        expires_at = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        expires_at_iso = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        if self.client and self.bucket:
            try:
                blob = self.bucket.blob(object_key)
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=expiration_minutes),
                    method="PUT",
                    content_type=content_type,
                )
                return {
                    "method": "PUT",
                    "signed_url": url,
                    "required_headers": {"Content-Type": content_type},
                    "expires_at": expires_at_iso,
                }
            except Exception as e:
                logger.error(f"Error generando URL firmada real en GCS: {e}")
                # Fallback a mock en caso de error
        
        # URL firmada Mock para desarrollo local
        mock_url = (
            f"https://storage.googleapis.com/{self.bucket_name}/{object_key}"
            f"?X-Goog-Algorithm=GOOG4-RSA-SHA256"
            f"&X-Goog-Date={datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
            f"&X-Goog-Expires={expiration_minutes * 60}"
            f"&X-Goog-SignedHeaders=content-type%3Bhost"
            f"&X-Goog-Signature=mock_v4_signature_for_testing"
        )
        return {
            "method": "PUT",
            "signed_url": mock_url,
            "required_headers": {"Content-Type": content_type},
            "expires_at": expires_at_iso,
        }

    def generate_download_url(self, object_key: str, expiration_minutes: int = 5) -> Dict[str, Any]:
        """Generar URL firmada V4 para descarga (método GET)"""
        expires_at = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        expires_at_iso = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        if self.client and self.bucket:
            try:
                blob = self.bucket.blob(object_key)
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=expiration_minutes),
                    method="GET",
                )
                return {
                    "url": url,
                    "expires_at": expires_at_iso,
                }
            except Exception as e:
                logger.error(f"Error generando URL de descarga en GCS: {e}")

        # URL mock
        mock_url = (
            f"https://storage.googleapis.com/{self.bucket_name}/{object_key}"
            f"?X-Goog-Algorithm=GOOG4-RSA-SHA256"
            f"&X-Goog-Expires={expiration_minutes * 60}"
            f"&X-Goog-Signature=mock_download_signature"
        )
        return {
            "url": mock_url,
            "expires_at": expires_at_iso,
        }

    def verify_object_exists(self, object_key: str) -> bool:
        """Verificar si el objeto existe en GCS"""
        if self.client and self.bucket:
            try:
                blob = self.bucket.blob(object_key)
                return blob.exists()
            except Exception as e:
                logger.warning(f"Error consultando objeto en GCS: {e}")
                return True
        # En modo mock asumimos que el objeto fue subido exitosamente
        return True

storage_service = StorageService()
