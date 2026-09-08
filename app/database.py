"""
Database configuration and session management.
Supports both SQLite (local) and PostgreSQL (production).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

from app.config import settings

# Create engine based on database URL
# SQLite needs special handling for concurrent access
if settings.database_is_sqlite:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
        echo=False,
    )
else:
    # PostgreSQL or other databases
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False,
    )

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for all models
Base = declarative_base()


def get_db():
    """
    Dependency for getting database sessions.
    Yields a session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables.
    Should be called at application startup.
    """
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized: {settings.DATABASE_URL}")


def init_test_db():
    """
    Initialize database for testing.
    Creates tables in the test database.
    """
    Base.metadata.create_all(bind=engine)
