"""Authentication gates for financial data APIs."""

from fastapi.testclient import TestClient

from app.main import app

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
