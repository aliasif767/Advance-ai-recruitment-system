"""
backend/app/core/config.py
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    GROQ_API_KEY: str = ""

    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "iars_recruitment"

    # Email (inbox that receives CVs)
    EMAIL_USER: str = ""           # 2020n07689@gmail.com
    EMAIL_PASS: str = ""           # Gmail App Password
    IMAP_SERVER: str = "imap.gmail.com"
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SAVE_FOLDER: str = "received_cvs"

    # Email watcher settings
    EMAIL_CHECK_INTERVAL: int = 30    # seconds between inbox checks
    EMAIL_WATCHER_ENABLED: bool = True # set False to disable auto-watcher

    # LinkedIn
    LINKEDIN_ACCESS_TOKEN: str = ""

    # GitHub
    GITHUB_TOKEN: str = ""

    # App
    SECRET_KEY: str = "changeme-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Scoring thresholds
    MATCH_THRESHOLD: int = 70
    MAYBE_THRESHOLD: int = 50
    INTERVIEWER_EMAIL: str = "hr@company.com"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()