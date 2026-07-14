"""
backend/app/main.py
FastAPI entry point.
On startup: connects MongoDB AND launches the background email watcher.
The email watcher checks inbox every 30 seconds automatically.

NOTE: When ENVIRONMENT=production (Vercel serverless), the email watcher
background task is intentionally disabled — serverless functions have no
persistent runtime between requests. Set EMAIL_WATCHER_ENABLED=True on a
dedicated always-on server (Railway, Render, VPS) to keep the watcher alive.
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

# Detect serverless / production environment
_IS_SERVERLESS = settings.ENVIRONMENT.lower() in ("production", "serverless", "vercel")

_watcher_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _watcher_task

    # ── Startup ───────────────────────────────────────────────────────────────
    await connect_mongo()
    logger.info("✅ MongoDB connected")

    # Launch background email watcher ONLY in local / non-serverless environments
    if settings.EMAIL_WATCHER_ENABLED and not _IS_SERVERLESS:
        from app.services.email_watcher import run_email_watcher
        _watcher_task = asyncio.create_task(run_email_watcher())
        logger.info(f"✅ Email watcher started — watching: {settings.EMAIL_USER}")
        logger.info(f"   Checking inbox every {settings.EMAIL_CHECK_INTERVAL} seconds")
    else:
        logger.info(
            "ℹ️  Email watcher DISABLED "
            f"(ENVIRONMENT={settings.ENVIRONMENT}, EMAIL_WATCHER_ENABLED={settings.EMAIL_WATCHER_ENABLED})"
        )

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

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow localhost (dev) + any configured FRONTEND_ORIGIN (production Vercel URL)
_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
]
if settings.FRONTEND_ORIGIN and settings.FRONTEND_ORIGIN not in _allowed_origins:
    _allowed_origins.append(settings.FRONTEND_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # allow all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import FileResponse

# Mount static frontend ONLY in local/non-serverless mode
# On Vercel the frontend is served as a static site — no need to mount it here
if not _IS_SERVERLESS:
    frontend_build = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    if os.path.exists(frontend_build):
        # Mount assets folder
        assets_dir = os.path.join(frontend_build, "assets")
        if os.path.exists(assets_dir):
            app.mount("/app/assets", StaticFiles(directory=assets_dir), name="assets")

        # Serve index.html as a catch-all for SPA routes under /app
        @app.get("/app/{full_path:path}", include_in_schema=False)
        @app.get("/app", include_in_schema=False)
        async def serve_spa(full_path: str = ""):
            return FileResponse(os.path.join(frontend_build, "index.html"))

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