from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_serves_browser_application() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Personal Finance Advisor" in response.text


def test_health_returns_healthy() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_browser_application_sets_security_headers() -> None:
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_static_application_script_is_served() -> None:
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "Authorization" in response.text
