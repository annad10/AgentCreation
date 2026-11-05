# Verify the health endpoint and the HTML page served by the backend.
from fastapi.testclient import TestClient
from backend.main import app

def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

def test_home_page():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Course Match" in response.text
