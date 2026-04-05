"""
backend/app/main.py
FastAPI entry point.
On startup: connects MongoDB AND launches the background email watcher.
The email watcher checks inbox every 30 seconds automatically.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.logger import get_logger
from app.db.mongo import connect_mongo, close_mongo

logger = get_logger(__name__)

_watcher_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _watcher_task

    # ── Startup ───────────────────────────────────────────────────────────────
    await connect_mongo()
    logger.info("✅ MongoDB connected")

    # Launch background email watcher
    from app.services.email_watcher import run_email_watcher
    _watcher_task = asyncio.create_task(run_email_watcher())
    logger.info(f"✅ Email watcher started — watching: {settings.EMAIL_USER}")
    logger.info(f"   Checking inbox every {settings.EMAIL_CHECK_INTERVAL} seconds")
    logger.info("✅ IARS API ready — fully automated recruitment pipeline active")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    if _watcher_task:
        _watcher_task.cancel()
        try:
            await _watcher_task
        except asyncio.CancelledError:
            pass
    await close_mongo()
    logger.info("IARS API shut down cleanly.")


app = FastAPI(
    title="IARS — Intelligent Agentic Recruitment System",
    description="Fully automated AI recruitment pipeline — email watcher + MongoDB",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static frontend (if built)
frontend_build = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(frontend_build):
    app.mount("/app", StaticFiles(directory=frontend_build, html=True), name="frontend")

# API routes
from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "env": settings.ENVIRONMENT,
        "db": "mongodb",
        "email_watcher": settings.EMAIL_WATCHER_ENABLED,
        "watching": settings.EMAIL_USER,
        "check_interval_seconds": settings.EMAIL_CHECK_INTERVAL,
    }


@app.get("/watcher/status", tags=["System"])
async def watcher_status():
    """Check if the email watcher is running."""
    running = _watcher_task is not None and not _watcher_task.done()
    return {
        "watcher_running": running,
        "email_account": settings.EMAIL_USER,
        "check_interval_seconds": settings.EMAIL_CHECK_INTERVAL,
        "cv_save_folder": settings.SAVE_FOLDER,
        "match_threshold": settings.MATCH_THRESHOLD,
        "maybe_threshold": settings.MAYBE_THRESHOLD,
    }