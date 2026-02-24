# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_mod
from app.database import Base


@pytest.fixture(scope="session")
def test_engine():
    # In-memory SQLite that persists for the test session
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture(scope="session")
def TestingSessionLocal(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db(test_engine):
    # IMPORTANT: make the app use the test engine for startup table creation too
    main_mod.engine = test_engine
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session(TestingSessionLocal):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    # Override the app dependency to use the test session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    main_mod.app.dependency_overrides[main_mod.get_db] = override_get_db

    with TestClient(main_mod.app) as c:
        yield c

    main_mod.app.dependency_overrides.clear()
