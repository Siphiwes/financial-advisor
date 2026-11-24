from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_application_information() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "application": "Financial Advisor API",
        "status": "running",
        "version": "0.1.0",
    }


def test_health_returns_healthy() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}



def test_web_workspace_is_served() -> None:
    response = client.get("/app")

    assert response.status_code == 200
    assert "Financial Advisor" in response.text



def test_web_assets_are_served() -> None:
    javascript = client.get("/assets/app.js")
    stylesheet = client.get("/assets/app.css")

    assert javascript.status_code == 200
    assert "Authorization" in javascript.text
    assert stylesheet.status_code == 200
    assert ".topbar" in stylesheet.text



def test_security_headers_are_applied() -> None:
    response = client.get("/app")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]



def test_private_api_responses_are_not_cached() -> None:
    response = client.get("/api/v1/privacy/export")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
