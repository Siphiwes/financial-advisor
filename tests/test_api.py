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
