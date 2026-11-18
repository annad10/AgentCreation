from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}

def test_home_and_assets():
    response = client.get("/")
    assert response.status_code == 200
    assert "Course Match" in response.text
    assert 'id="course-form"' in response.text
    for path in ("/static/style.css", "/static/app.js"):
        assert client.get(path).status_code == 200

def test_comparison_discloses_limitations():
    page = client.get("/").text
    assert "Keyword comparison" in page
    assert 'id="comparison-mode"' in page
    assert 'id="ai-consent"' in page
