"""Authentication requirements for password and session controls."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_password_change_requires_authentication() -> None:
    response = client.post(
        "/auth/password/change",
        json={
            "current_password": "current-password-placeholder",
            "new_password": "replacement-password-placeholder",
        },
    )
    assert response.status_code == 401


def test_session_revocation_requires_authentication() -> None:
    response = client.post(
        "/auth/sessions/revoke",
        json={"current_password": "current-password-placeholder"},
    )
    assert response.status_code == 401
