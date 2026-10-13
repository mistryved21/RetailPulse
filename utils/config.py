"""Application configuration using pydantic-settings."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """RetailPulse application settings loaded from .env file."""
    # Database
    DATABASE_URL: str = "postgresql+psycopg2://retailpulse:retailpulse123@localhost:5432/retailpulse_db"
    
    # LLM
    LLM_PROVIDER: str = "gemini"  # openai / gemini / ollama
    MODEL_MODE: str = "base"      # base / tuned
    TUNED_GEMINI_MODEL: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    
    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    
    # App
    APP_NAME: str = "RetailPulse"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    REPORTS_DIR: str = "./reports"
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

settings = get_settings()
