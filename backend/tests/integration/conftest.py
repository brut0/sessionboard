"""Testcontainers PostgreSQL fixtures and session setup for integration tests."""

import os

import pytest
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

import app.db
from alembic import command
from app.config import get_settings


@pytest.fixture(scope="session")
def postgres_container():
    """Start an ephemeral PostgreSQL 16 container for the test session."""
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        connection_url = postgres.get_connection_url()
        os.environ["DATABASE_URL"] = connection_url
        os.environ["APP_ENV"] = "test"
        os.environ["OTEL_SDK_DISABLED"] = "true"

        get_settings.cache_clear()
        app.db.engine = create_engine(connection_url, pool_pre_ping=True)
        app.db.SessionLocal.configure(bind=app.db.engine)

        # Run Alembic upgrade head
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", connection_url)
        command.upgrade(alembic_cfg, "head")

        yield postgres


@pytest.fixture
def db_engine(postgres_container):
    return app.db.engine


@pytest.fixture
def db_session(db_engine):
    """Provide a clean transactional session per test with automatic rollback."""
    connection = db_engine.connect()
    transaction = connection.begin()
    TestSessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = TestSessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
