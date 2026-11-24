"""Security checks for the watsonx advisor feature gate and consent."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.schemas.auth import AuthenticatedUser

client = TestClient(app)


def _authenticated_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=str(uuid4()),
        email="owner@example.com",
        created_at=datetime.now(UTC),
    )


def test_advisor_requires_separate_ai_feature_gate(monkeypatch) -> None:
    monkeypatch.setenv("FINANCIAL_DATA_ENABLED", "true")
    monkeypatch.setenv("FINANCIAL_AI_ENABLED", "false")
    app.dependency_overrides[get_current_user] = _authenticated_user

    try:
        response = client.post(
            "/api/v1/advisor/chat",
            json={
                "question": "Explain the available summary.",
                "consent_to_share_summary": True,
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 503
    assert "not enabled" in response.json()["detail"]


def test_advisor_requires_explicit_consent_before_summary_lookup(monkeypatch) -> None:
    monkeypatch.setenv("FINANCIAL_DATA_ENABLED", "true")
    monkeypatch.setenv("FINANCIAL_AI_ENABLED", "true")
    app.dependency_overrides[get_current_user] = _authenticated_user

    try:
        response = client.post(
            "/api/v1/advisor/chat",
            json={
                "question": "Explain the available summary.",
                "consent_to_share_summary": False,
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 400
    assert "consent" in response.json()["detail"].casefold()



def test_transaction_category_suggestion_requires_separate_consent(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FINANCIAL_DATA_ENABLED", "true")
    monkeypatch.setenv("FINANCIAL_AI_ENABLED", "true")
    app.dependency_overrides[get_current_user] = _authenticated_user

    try:
        response = client.post(
            "/api/v1/advisor/transactions/"
            "0123456789abcdef0123456789abcdef/suggest-category",
            json={"consent_to_share_transaction": False},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 400
    assert "consent" in response.json()["detail"].casefold()
