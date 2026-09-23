from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # FastAPI
    APP_NAME: str = "WellQ Clinical Tests API"
    DEBUG: bool = False
    
    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "wellq_clinical"
    
    # Google Cloud Storage
    GCS_PROJECT_ID: str
    GCS_BUCKET_NAME: str
    GCS_CREDENTIALS_PATH: Optional[str] = None  # JSON credentials
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Upload
    MAX_CLINICAL_FILE_BYTES: int = 20 * 1024 * 1024  # 20 MB
    ALLOWED_MIME_TYPES: list = ["application/pdf", "image/jpeg", "image/png", "image/heic"]
    
    # GCS URLs
    SIGNED_URL_EXPIRATION_MINUTES: int = 15
    DOWNLOAD_URL_EXPIRATION_MINUTES: int = 5
    
    # Rate limiting (por paciente)
    MAX_PENDING_UPLOADS: int = 10
    MAX_URL_REFRESHES_PER_UPLOAD: int = 10
    MAX_DOWNLOADS_PER_HOUR: int = 100
    
    # Malware scanning (integración futura)
    ENABLE_MALWARE_SCAN: bool = True
    MALWARE_SCAN_TIMEOUT_SECONDS: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()