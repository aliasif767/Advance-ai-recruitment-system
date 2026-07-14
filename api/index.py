"""
api/index.py
Vercel Python Serverless entry point.

Vercel natively supports FastAPI ASGI apps exported as `app`.
We re-export the existing FastAPI instance from backend/app/main.py.

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

# ── Export FastAPI app for Vercel Python runtime ──────────────────────────────
from app.main import app  # noqa: E402
