"""Authentication gates for financial data APIs."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.schemas.auth import AuthenticatedUser

client = TestClient(app)


def test_financial_accounts_require_authentication() -> None:
    assert client.get("/api/v1/accounts").status_code == 401


def test_financial_transactions_require_authentication() -> None:
    assert client.get("/api/v1/transactions").status_code == 401


def test_financial_summary_requires_authentication() -> None:
    assert client.get("/api/v1/analytics/summary").status_code == 401


def test_fnb_import_confirmation_requires_authentication() -> None:
    response = client.post(
        "/imports/fnb/csv/confirm",
        data={"account_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "consent": "true"},
        files={"file": ("statement.csv", b"", "text/csv")},
    )

    assert response.status_code == 401



def test_financial_data_gate_returns_503_after_authentication(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FINANCIAL_DATA_ENABLED", "false")
    authenticated_user = AuthenticatedUser(
        id=str(uuid4()),
        email="owner@example.com",
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_current_user] = lambda: authenticated_user

    try:
        response = client.get("/api/v1/accounts")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].casefold()


def test_debt_endpoints_require_authentication() -> None:
    assert client.get("/api/v1/debts").status_code == 401
    assert client.get("/api/v1/analytics/debts").status_code == 401
