"""
Vercel API Entry Point

This file is used by Vercel to serve the FastAPI application.

For local development, use: uvicorn app.main:app --reload
For Vercel deployment, this file exposes the app correctly.

The FastAPI app is imported from app.main and adapted for Vercel's
serverless environment.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import init_db
from app.config import settings


def handler(request):
    """
    Vercel handler function.

    This function is called by Vercel for each request.
    It initializes the database on first request (cold start)
    and then forwards the request to FastAPI.
    """
    # Initialize database on cold start
    # Note: In serverless, we may want to lazy-init or use connection pooling
    if settings.ENVIRONMENT != "test":
        try:
            init_db()
        except Exception:
            pass  # Database may already be initialized

    # Return the FastAPI app
    # Vercel's Python runtime handles ASGI apps
    return app


# For Vercel, we need to expose the app directly
# Vercel will use this as the entry point
app = handler(None) if False else app


# The following makes this file compatible with both:
# 1. Vercel deployment (api/index.py as entry point)
# 2. Local development (imports work correctly)

# Ensure the database is initialized
if not app.openapi_urls:  # type: ignore
    try:
        init_db()
    except Exception:
        pass
