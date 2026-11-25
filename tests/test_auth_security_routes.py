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


def test_logout_clears_secure_http_only_session_cookie() -> None:
    response = client.post("/auth/logout")

    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    assert "finance_access_token=" in cookie
    assert "max-age=0" in cookie
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie


def test_cookie_authenticated_state_change_requires_same_origin() -> None:
    secure_client = TestClient(client.app, base_url="https://testserver")
    secure_client.cookies.set(
        "finance_access_token",
        "invalid-session-token",
    )

    response = secure_client.post(
        "/auth/password/change",
        json={
            "current_password": "current-password-placeholder",
            "new_password": "replacement-password-placeholder",
        },
    )

    assert response.status_code == 403
