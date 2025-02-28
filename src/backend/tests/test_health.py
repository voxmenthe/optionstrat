import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.main import app

def test_health_check():
    """Test the health check endpoint."""
    # Create a test client manually
    client = TestClient(app)
    
    # Make the request
    response = client.get("/health")
    
    # Verify the response
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"} 