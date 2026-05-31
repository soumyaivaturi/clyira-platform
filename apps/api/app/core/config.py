"""
Clyira Application Configuration
Central configuration management using pydantic-settings
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Clyira"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://clyira_admin:clyira_dev_2026@localhost:5432/clyira"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Groq (LLaMA — primary LLM, generous free tier)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Gemini (Google AI — primary for deep LLM analysis, 1,500 req/day free)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MAX_TOKENS: int = 16384

    # Anthropic (Claude API) — kept for backwards compatibility
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_MAX_TOKENS: int = 8192

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # File Storage (local fallback for dev)
    STORAGE_PATH: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: str = "pdf,docx,xlsx,doc,xls"

    # Supabase (cloud storage in production)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "documents"

    # Email (Resend — https://resend.com, free tier 3,000/month)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Clyira <notifications@clyira.ai>"
    EMAIL_ENABLED: bool = True  # Set False to disable all emails regardless of API key

    # Assessment Engine
    ASSESSMENT_TIMEOUT_SECONDS: int = 300
    MAX_CONCURRENT_ASSESSMENTS: int = 5
    ENFORCEMENT_MATCH_THRESHOLD: float = 0.75

    # Embedding
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384  # Updated if using different model

    def validate_production_secrets(self) -> None:
        """Raise at startup if critical secrets are missing in production."""
        if self.ENVIRONMENT == "production":
            if not self.SECRET_KEY:
                raise ValueError("SECRET_KEY must be set in production")
            if self.SECRET_KEY == "clyira-dev-secret-key-change-in-production":
                raise ValueError("SECRET_KEY must not use the default development value in production")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def allowed_file_types_list(self) -> list[str]:
        return [ft.strip() for ft in self.ALLOWED_FILE_TYPES.split(",")]

    class Config:
        env_file = "../../.env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
