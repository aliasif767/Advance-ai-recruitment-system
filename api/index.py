"""
api/index.py
Vercel Python Serverless entry point.

Vercel's Python runtime calls this as an AWS Lambda-compatible handler.
We use Mangum to bridge ASGI (FastAPI) → WSGI/Lambda interface, which
correctly reconstructs the original request path from the Vercel rewrite
(e.g. /api/v1/jobs/ → /api/index.py preserves path as /api/v1/jobs/).

Without Mangum, Vercel's default handler passes a mangled path that causes
FastAPI to return 404 on every route.

Python path note:
  Vercel runs this file from the repo root, so we add `backend/` to sys.path
  so that `from app.xxx import ...` works exactly as in local development.
"""
import os
import sys

# ── Make backend importable ───────────────────────────────────────────────────
# Vercel executes from the repo root. Adding backend/ lets us import `app.*`
# the same way as when uvicorn runs from the backend/ directory.
_backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_backend_dir))

# ── Import FastAPI app ────────────────────────────────────────────────────────
from app.main import app  # noqa: E402

# ── Wrap with Mangum for Vercel's Lambda-compatible runtime ───────────────────
# lifespan="off" because Vercel serverless functions don't support persistent
# startup/shutdown hooks between invocations — MongoDB is connected lazily.
from mangum import Mangum  # noqa: E402

handler = Mangum(app, lifespan="auto")
