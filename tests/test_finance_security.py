"""Authentication boundaries for financial and AI endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_financial_account_routes_require_authentication() -> None:
    assert client.get("/api/v1/accounts").status_code == 401


def test_transaction_routes_require_authentication() -> None:
    assert client.get("/api/v1/transactions").status_code == 401


def test_budget_and_goal_routes_require_authentication() -> None:
    assert client.get("/api/v1/budgets/progress?period=2026-11").status_code == 401
    assert client.get("/api/v1/goals").status_code == 401


def test_import_preview_and_confirmation_require_authentication() -> None:
    preview = client.post(
        "/imports/fnb/csv/preview",
        files={"file": ("statement.csv", b"", "text/csv")},
    )
    confirm = client.post(
        "/imports/fnb/csv/confirm",
        data={"account_id": "00000000000000000000000000000001"},
        files={"file": ("statement.csv", b"", "text/csv")},
    )

    assert preview.status_code == 401
    assert confirm.status_code == 401


def test_import_history_requires_authentication() -> None:
    assert client.get("/imports/fnb/imports").status_code == 401


def test_ai_consent_and_advisor_routes_require_authentication() -> None:
    assert client.get("/api/v1/privacy/ai-consent").status_code == 401
    assert client.put(
        "/api/v1/privacy/ai-consent",
        json={"consent": True},
    ).status_code == 401
    assert client.post(
        "/api/v1/advisor/ask",
        json={
            "question": "Explain the financial summary.",
            "from_date": "2026-11-01",
            "to_date": "2026-11-24",
            "currency": "ZAR",
        },
    ).status_code == 401
