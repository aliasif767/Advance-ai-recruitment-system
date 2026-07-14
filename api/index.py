"""
api/index.py
Vercel Python Serverless entry point.

Vercel expects a handler at api/index.py that can serve HTTP requests.
We use `mangum` as the ASGI → AWS Lambda / Vercel adapter, which wraps
our existing FastAPI `app` instance without any changes to business logic.

Python path note:
  Vercel runs this file from the repo root, so we add `backend/` to sys.path
  so that `from app.xxx import ...` works exactly as in local development.
"""
import sys
import os

# ── Make backend importable ───────────────────────────────────────────────────
# Vercel executes from the repo root. Adding backend/ lets us import `app.*`
# the same way as when uvicorn runs from the backend/ directory.
_backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_backend_dir))

# ── Import the FastAPI app ────────────────────────────────────────────────────
from app.main import app  # noqa: E402  (import after sys.path manipulation)

# ── Wrap with Mangum (ASGI → serverless handler) ─────────────────────────────
from mangum import Mangum  # noqa: E402

handler = Mangum(app, lifespan="off")
