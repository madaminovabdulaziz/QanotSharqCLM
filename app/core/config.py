"""
Configuration Settings
Load environment variables and app configuration
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Layover Management System"
    ENV: str = "development"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost/layover_db"
    
    # Security
    SECRET_KEY: str 
    JWT_SECRET_KEY: str 
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 8

    ACCESS_TOKEN_EXPIRE_MINUTES: int
    API_VERSION: str
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Frontend URL (for generating links in emails)
    FRONTEND_URL: str = "http://localhost:8000"
    
    # SMTP Email Settings
    SMTP_HOST: str 
    SMTP_PORT: int 
    SMTP_TLS: bool 
    SMTP_USER: str 
    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str 
    SMTP_FROM_NAME: str 
    
    # Support Contact (ADD THIS LINE)
    SUPPORT_EMAIL: str = ""  # <-- ADD THIS
    
    # WhatsApp Settings (Optional)
    WHATSAPP_ENABLED: bool = False
    WHATSAPP_API_KEY: str = ""
    WHATSAPP_FROM_NUMBER: str = ""
    
    # SMS Settings (Optional)
    SMS_ENABLED: bool = False
    SMS_API_KEY: str = ""
    SMS_FROM_NUMBER: str = ""
    
    # File Upload
    MAX_FILE_SIZE_MB: int = 5
    ALLOWED_FILE_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/jpeg",
        "image/png",
    ]
    
    # S3/MinIO Storage (for file attachments)
    STORAGE_BACKEND: str = "local"  # or "s3"
    S3_BUCKET: str = "layover-files"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_ENDPOINT: str = ""
    S3_REGION: str = "us-east-1"
    
    # Reminder & Escalation Settings (defaults, overridden by station config)
    DEFAULT_FIRST_REMINDER_HOURS: int = 12
    DEFAULT_SECOND_REMINDER_HOURS: int = 24
    DEFAULT_ESCALATION_HOURS: int = 36
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 25
    MAX_PAGE_SIZE: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()