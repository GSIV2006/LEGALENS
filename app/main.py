"""
Legal Metrology Compliance Assessment System
FastAPI Application Entry Point

Smart India Hackathon 2026
"Software System to Check Compliance of Packaged Commodities
under Legal Metrology (Packaged Commodities) Rules, 2011"
"""
import os
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db, init_test_db, SessionLocal, Base
from app.routers import (
    auth_router,
    products_router,
    inspections_router,
    rules_router,
    reports_router,
    dashboard_router,
    history_router,
)
from app.schemas.dashboard import DashboardSummary


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title="Legal Metrology Compliance System",
        description="""
        Software System to Check Compliance of Packaged Commodities
        under Legal Metrology (Packaged Commodities) Rules, 2011

        ## Features
        - JWT Authentication with role-based access (ADMIN, INSPECTOR, VIEWER)
        - Product management
        - Inspection management with image upload
        - OCR integration layer (mock for now, ready for PaddleOCR)
        - Field extraction from OCR text
        - Legal rule engine with configurable rules
        - Compliance checking engine
        - Manual inspector overrides
        - PDF and DOCX report generation
        - Dashboard with statistics
        - Audit logging

        ## Database
        - SQLite for local development
        - PostgreSQL for production/Vercel (via DATABASE_URL env var)

        ## OCR Integration
        The OCR service is a mock implementation. Our OCR teammates will
        replace it with real PaddleOCR/OpenCV. The rest of the backend
        continues to work without modification.
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS
    configure_cors(app)

    # Include routers
    include_routers(app)

    # Mount static files (uploads)
    configure_static_files(app)

    # Add exception handlers
    add_exception_handlers(app)

    # Add startup/shutdown events
    add_lifecycle_events(app)

    return app


def configure_cors(app: FastAPI):
    """
    Configure CORS middleware.

    Allows requests from:
    - http://localhost:3000 (React default)
    - http://localhost:5173 (Vite default)
    - FRONTEND_URL environment variable (production)
    """
    # Get allowed origins
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://10.189.236.68:5173",
    ]

    frontend_url = settings.FRONTEND_URL
    if frontend_url and frontend_url not in allowed_origins:
        allowed_origins.append(frontend_url)

    # Also allow the origin without trailing slash
    allowed_origins = list(set(allowed_origins))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )


def include_routers(app: FastAPI):
    """
    Include all API routers.
    """
    app.include_router(auth_router)
    app.include_router(products_router)
    app.include_router(inspections_router)
    app.include_router(rules_router)
    app.include_router(reports_router)
    app.include_router(dashboard_router)
    app.include_router(history_router)


def configure_static_files(app: FastAPI):
    """
    Configure static file serving for uploads.

    In production/Vercel, this may be configured differently.
    """
    upload_dir = settings.UPLOAD_DIR

    if upload_dir.exists():
        app.mount(
            "/uploads",
            StaticFiles(directory=str(upload_dir)),
            name="uploads",
        )


def add_exception_handlers(app: FastAPI):
    """
    Add custom exception handlers.
    """

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Global exception handler to prevent stack traces in production.
        """
        # Log the exception (in production, use proper logging)
        print(f"Unhandled exception: {exc}")

        # Return generic error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal error occurred. Please try again later.",
                "status": "error",
            },
        )


def add_lifecycle_events(app: FastAPI):
    """
    Add startup and shutdown event handlers.
    """

    @app.on_event("startup")
    async def startup():
        """
        Application startup handler.

        Initializes database tables.
        """
        # Initialize database
        try:
            init_db()
            print(f"Database initialized: {settings.DATABASE_URL}")
        except Exception as e:
            print(f"Database initialization warning: {e}")

        # Print startup info
        print(f"\n{'='*60}")
        print(f"  Legal Metrology Compliance System")
        print(f"{'='*60}")
        print(f"  Environment: {settings.ENVIRONMENT}")
        print(f"  Database: {settings.DATABASE_URL}")
        print(f"  OCR Engine: mock (ready for PaddleOCR)")
        print(f"  Storage Mode: {settings.STORAGE_MODE}")
        print(f"{'='*60}\n")

    @app.on_event("shutdown")
    async def shutdown():
        """
        Application shutdown handler.
        """
        print("Shutting down...")


# Create application instance
app = create_app()


# ================ HEALTH CHECK ENDPOINT ================

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns status of:
    - Application
    - Database connection
    - OCR service status
    """
    # Check database
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
    except Exception:
        db_status = "disconnected"

    # Check OCR status
    ocr_status = "mock"

    return {
        "status": "ok",
        "database": db_status,
        "ocr": ocr_status,
        "storage_mode": settings.STORAGE_MODE,
        "environment": settings.ENVIRONMENT,
    }


# ================ ROOT ENDPOINT ================

@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information.
    """
    return {
        "name": "Legal Metrology Compliance System",
        "version": "1.0.0",
        "description": "Smart India Hackathon 2026 Project",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


# ================ STATIC UPLOAD FOLDER CREATION ================

def ensure_upload_folders():
    """
    Ensure upload folders exist.
    Called on startup.
    """
    upload_dir = settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Create view type subdirectories
    for view_type in ["front", "back", "left", "right", "top", "bottom", "other"]:
        view_dir = upload_dir / view_type
        view_dir.mkdir(parents=True, exist_ok=True)

    # Create .gitkeep files
    gitkeep = upload_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()

    for view_type in ["front", "back", "left", "right", "top", "bottom", "other"]:
        view_dir = upload_dir / view_type
        gitkeep = view_dir / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()


# Call on module load
ensure_upload_folders()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
