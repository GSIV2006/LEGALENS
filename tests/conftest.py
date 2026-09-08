"""
Pytest configuration and fixtures for testing.
"""
import os
import sys
from typing import Generator, Optional

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import Base, get_db
from app.utils.helpers import generate_password_hash


# Test database settings
TEST_DATABASE_URL = "sqlite:///./test_legal_metrology.db"


@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_db_engine) -> Generator:
    """Create database session for testing."""
    connection = test_db_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session) -> Generator:
    """Create test client with database dependency override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    from app.main import app
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    """Create admin user for testing."""
    from app.models import User

    admin = User(
        email="admin@test.com",
        username="admin_test",
        hashed_password=generate_password_hash("admin123"),
        full_name="Test Admin",
        role="ADMIN",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def inspector_user(db_session):
    """Create inspector user for testing."""
    from app.models import User

    inspector = User(
        email="inspector@test.com",
        username="inspector_test",
        hashed_password=generate_password_hash("inspector123"),
        full_name="Test Inspector",
        role="INSPECTOR",
        is_active=True,
    )
    db_session.add(inspector)
    db_session.commit()
    db_session.refresh(inspector)
    return inspector


@pytest.fixture
def viewer_user(db_session):
    """Create viewer user for testing."""
    from app.models import User

    viewer = User(
        email="viewer@test.com",
        username="viewer_test",
        hashed_password=generate_password_hash("viewer123"),
        full_name="Test Viewer",
        role="VIEWER",
        is_active=True,
    )
    db_session.add(viewer)
    db_session.commit()
    db_session.refresh(viewer)
    return viewer


@pytest.fixture
def auth_headers(client, admin_user) -> dict:
    """Get authentication headers for admin user."""
    response = client.post(
        "/auth/login/json",
        json={
            "email": "admin@test.com",
            "password": "admin123",
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def product(db_session) -> Generator:
    """Create a sample product for testing."""
    from app.models import Product

    product = Product(
        product_name="Test Product",
        brand="Test Brand",
        category="Test Category",
        manufacturer="Test Manufacturer",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    yield product


@pytest.fixture
def another_product(db_session) -> Generator:
    """Create another sample product."""
    from app.models import Product

    product = Product(
        product_name="Another Test Product",
        brand="Another Brand",
        category="Another Category",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    yield product
