import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient


# Create an in-memory SQLite database for testing
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Create all tables in the test database
Base.metadata.create_all(bind=engine)


# Override the get_db dependency for testing
@pytest.fixture
def test_db():
    """Create a test database session."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    yield session
    
    # Rollback the transaction and close the connection
    session.close()
    transaction.rollback()
    connection.close()


# Override the get_db dependency for testing
def override_get_db():
    """Override the get_db dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create a test client with the overridden dependency
@pytest.fixture
def client():
    """Create a test client with the overridden dependency."""
    try:
        # Set up dependency override
        app.dependency_overrides[get_db] = override_get_db
        
        # Create client without context manager
        client = TestClient(app)
        
        yield client
    finally:
        # Clean up dependencies
        app.dependency_overrides = {} 