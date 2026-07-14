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

    # ── Assessment Module ──────────────────────────────────────────────────────
    # Set True to auto-send assessment to MATCH candidates (replaces old interview invite)
    AUTO_SEND_ASSESSMENT: bool = True

    # Assessment portal base URL — candidates receive this link (should point to frontend)
    # On Vercel, override this with your actual deployment URL e.g. https://iars.vercel.app
    ASSESSMENT_BASE_URL: str = "http://localhost:3000"

    # Assessment timing
    ASSESSMENT_DURATION_MINUTES: int = 60
    ASSESSMENT_EXPIRY_HOURS: int = 72         # link expires after N hours
    PER_QUESTION_TIME_SECONDS: int = 120      # default per-question timer

    # Question generation defaults
    DEFAULT_QUESTION_COUNT: int = 30
    DEFAULT_EASY_COUNT: int = 10
    DEFAULT_MEDIUM_COUNT: int = 15
    DEFAULT_HARD_COUNT: int = 5

    # Code runner sandbox
    CODE_EXECUTION_TIMEOUT_MS: int = 5000
    CODE_EXECUTION_ENABLED: bool = True       # set False to skip actual code running

    # Proctoring
    ENABLE_PROCTORING: bool = True
    ENABLE_CAMERA: bool = False               # requires camera permission from candidate
    MAX_VIOLATIONS_BEFORE_FLAG: int = 5       # flag candidate after N violations
    CHEATING_PENALTY_PER_VIOLATION: int = 2   # points deducted per violation (max 20)

    # Composite scoring weights (must sum to 100)
    WEIGHT_RESUME: int = 25
    WEIGHT_MCQ: int = 25
    WEIGHT_CODING: int = 20
    WEIGHT_SHORT_ANSWER: int = 15
    WEIGHT_COMMUNICATION: int = 10
    WEIGHT_PROBLEM_SOLVING: int = 5

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
