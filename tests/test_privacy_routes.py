"""Tests for authenticated user export and deletion controls."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_user_for_deletion
from app.main import app
from app.schemas.auth import AuthenticatedUser
from app.services import finance

client = TestClient(app)


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=str(uuid4()),
        email="owner@example.com",
        created_at=datetime.now(UTC),
    )


def test_privacy_export_requires_authentication() -> None:
    response = client.get("/api/v1/privacy/export")
    assert response.status_code == 401


def test_privacy_delete_requires_authentication() -> None:
    response = client.delete("/api/v1/privacy/data")
    assert response.status_code == 401


def test_privacy_export_remains_available_when_finance_writes_are_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FINANCIAL_DATA_ENABLED", "false")
    app.dependency_overrides[get_current_user] = _user
    monkeypatch.setattr(
        finance,
        "export_user_data",
        lambda user: {
            "exported_at": datetime.now(UTC),
            "user_id": user.id,
            "email": user.email,
            "data": {
                "accounts": [],
                "transactions": [],
                "categories": [],
                "budgets": [],
                "goals": [],
                "imports": [],
                "audit": [],
            },
            "record_counts": {
                "accounts": 0,
                "transactions": 0,
                "categories": 0,
                "budgets": 0,
                "goals": 0,
                "imports": 0,
                "audit": 0,
            },
            "original_statement_files_included": False,
        },
    )

    try:
        response = client.get("/api/v1/privacy/export")
    finally:
        app.dependency_overrides.pop(get_user_for_deletion, None)

    assert response.status_code == 200
    assert response.json()["original_statement_files_included"] is False


def test_privacy_delete_remains_available_when_finance_writes_are_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FINANCIAL_DATA_ENABLED", "false")
    app.dependency_overrides[get_user_for_deletion] = _user
    monkeypatch.setattr(
        finance,
        "delete_user_data_and_account",
        lambda user, current_password: {
            "deleted": True,
            "deleted_record_counts": {
                "accounts": 0,
                "transactions": 0,
                "categories": 0,
                "budgets": 0,
                "goals": 0,
                "imports": 0,
                "audit": 0,
            },
            "account_access_revoked": True,
            "message": "The financial records and login account were deleted.",
        },
    )

    try:
        response = client.delete(
            "/api/v1/privacy/data",
            json={"current_password": "test-current-password"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["account_access_revoked"] is True



def test_audit_history_requires_authentication() -> None:
    response = client.get("/api/v1/privacy/audit")
    assert response.status_code == 401


def test_account_deletion_rechecks_password_before_any_record_deletion(
    monkeypatch,
) -> None:
    account_user = _user()
    monkeypatch.setattr(finance, "_connection", lambda: (object(), "finance-advisor-db"))
    monkeypatch.setattr(
        finance,
        "get_user_by_email",
        lambda client, database, email: {
            "_id": "user:email:opaque",
            "_rev": "revision",
            "type": "user",
            "user_id": account_user.id,
            "password_hash": "stored-password-hash",
        },
    )
    monkeypatch.setattr(finance, "verify_password", lambda password, stored_hash: False)
    monkeypatch.setattr(
        finance,
        "list_user_scoped_documents",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Deletion must not begin after failed password verification.")
        ),
    )

    import pytest

    with pytest.raises(finance.FinanceValidationError, match="current password"):
        finance.delete_user_data_and_account(account_user, "incorrect-current-password")
