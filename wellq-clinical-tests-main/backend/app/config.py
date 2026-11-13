"""Fail-closed configuration; no usable identity/storage defaults."""
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
    APP_NAME: str = "WellQ Clinical Tests API"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEBUG: bool = Field(False, validation_alias="WELLQ_DEBUG")
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "wellq_clinical"
    JWT_PUBLIC_KEY: Optional[str] = None
    JWT_ISSUER: Optional[str] = None
    JWT_AUDIENCE: Optional[str] = None
    JWT_ALGORITHM: Literal["RS256"] = "RS256"
    JWT_MAX_LIFETIME_SECONDS: int = Field(3600, ge=60, le=86400)
    CORS_ORIGINS: list[str] = []
    GCS_PROJECT_ID: Optional[str] = None
    GCS_BUCKET_NAME: Optional[str] = None
    GCS_CREDENTIALS_PATH: Optional[str] = None
    MAX_CLINICAL_FILE_BYTES: int = Field(20 * 1024 * 1024, gt=0)
    ALLOWED_MIME_TYPES: list[str] = ["application/pdf", "image/jpeg", "image/png", "image/heic"]
    SIGNED_URL_EXPIRATION_MINUTES: int = Field(15, ge=1, le=15)
    DOWNLOAD_URL_EXPIRATION_MINUTES: int = Field(5, ge=1, le=5)
    MAX_REQUESTS_PER_MINUTE: int = 120
    MAX_PENDING_UPLOADS: int = 10
    MAX_URL_REFRESHES_PER_UPLOAD: int = 10
    MAX_DOWNLOADS_PER_HOUR: int = 100
    CLAMAV_HOST: Optional[str] = None
    CLAMAV_PORT: int = 3310
    MALWARE_SCAN_TIMEOUT_SECONDS: int = 30
    MAX_DOCUMENT_PAGES: int = 30
    MAX_IMAGE_PIXELS: int = 40_000_000
    JOB_LEASE_SECONDS: int = 300
    JOB_MAX_ATTEMPTS: int = 5
    CATALOG_CLINICALLY_APPROVED: bool = False
    AI_PROVIDER_APPROVED: bool = False

    def validate_identity(self):
        if not all((self.JWT_PUBLIC_KEY, self.JWT_ISSUER, self.JWT_AUDIENCE)):
            raise RuntimeError("Trusted identity authority is not configured")
        if self.ENVIRONMENT == "production" and (
            self.JWT_ISSUER.strip().rstrip("/").lower()
            in {"https://identity.wellq-integration.invalid", "https://identity.wellq-capstone-demo.invalid"}
            or self.JWT_AUDIENCE.strip() in {"wellq-integration-only", "wellq-capstone-demo-only"}
        ):
            raise RuntimeError("Synthetic integration identity is forbidden in production")
        if "BEGIN PUBLIC KEY" not in self.JWT_PUBLIC_KEY:
            raise RuntimeError("RSA public verification key required")
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
        try:
            key = load_pem_public_key(self.JWT_PUBLIC_KEY.encode())
            if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
                raise ValueError()
        except (ValueError, TypeError):
            raise RuntimeError("RSA verification key of at least 2048 bits required")
        if "*" in self.CORS_ORIGINS:
            raise RuntimeError("Wildcard CORS forbidden")

settings = Settings()
