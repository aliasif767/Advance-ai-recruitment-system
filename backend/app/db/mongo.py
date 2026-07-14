"""
backend/app/db/mongo.py
Initializes MongoDB connection using Motor + Beanie ODM.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.db.mongo_models import (
    JobDocument, CandidateDocument, PipelineRunDocument,
    ActivityDocument, StatsDocument
)
from app.db.interview_models import (
    AssessmentDocument, QuestionDocument, AssessmentSessionDocument,
    ViolationLogDocument, EvaluationReportDocument, QuestionUploadDocument
)
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_client: AsyncIOMotorClient | None = None


async def connect_mongo():
    global _client

    _client = AsyncIOMotorClient(settings.MONGO_URI)

    db = _client.get_database(settings.MONGO_DB_NAME)

    await init_beanie(
        database=db,
        document_models=[
            # ── Existing ──────────────────────────────────────────────────────
            JobDocument,
            CandidateDocument,
            PipelineRunDocument,
            ActivityDocument,
            StatsDocument,
            # ── Assessment Module (new) ────────────────────────────────────────
            AssessmentDocument,
            QuestionDocument,
            AssessmentSessionDocument,
            ViolationLogDocument,
            EvaluationReportDocument,
            QuestionUploadDocument,
        ],
    )

    logger.info(f"MongoDB connected → {settings.MONGO_DB_NAME}")


async def close_mongo():
    """Call on FastAPI shutdown."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")

