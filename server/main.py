"""AgentOS — top-level entry point.

Run from the server/ directory:
    uvicorn main:app --reload

This file just adds backend/ to the Python path and re-exports the
FastAPI app that lives in backend/index.py. All routing, middleware,
and lifespan logic is defined there.
"""

import sys
import os

# Make bare imports inside backend/ work when running from server/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from backend.index import app  # noqa: E402  (must come after sys.path mutation)

__all__ = ["app"]
