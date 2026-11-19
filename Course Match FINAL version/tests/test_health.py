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
    assert response.text.count('class="panel-form"') == 2
    assert 'id="tab-syllabus"' in response.text and 'id="tab-recommend"' in response.text
    for path in ("/static/style.css", "/static/app.js"):
        assert client.get(path).status_code == 200

def test_comparison_discloses_limitations():
    page = client.get('/').text
    assert "Keyword comparison" in page
    # One fixed method for everyone: no method menus or AI consent boxes on the page.
    assert 'class="mode"' not in page and 'class="consent"' not in page
    assert 'id="rec-cv"' in page and 'id="rec-cv-pdf"' in page and 'id="syllabus-home"' in page


def test_pages_are_never_served_from_a_stale_browser_copy():
    for path in ("/", "/?refresh=6", "/static/app.js", "/static/style.css"):
        response = client.get(path)
        assert response.headers["cache-control"] == "no-cache", path
    assert client.get("/").text == client.get("/?refresh=6").text
