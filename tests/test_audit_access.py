from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.auth import AuthenticatedUser
from app.services import finance


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=str(uuid4()),
        email="owner@example.invalid",
        created_at=datetime.now(UTC),
    )


def test_sensitive_access_audit_contains_no_financial_payload(monkeypatch) -> None:
    user = _user()
    captured = {}

    class Client:
        pass

    monkeypatch.setattr(finance, "_connection", lambda: (Client(), "finance-advisor-db"))

    def capture(_client, _database, user_id, collection, data):
        captured.update(
            {
                "user_id": user_id,
                "collection": collection,
                "data": data,
            }
        )
        return "record-id"

    monkeypatch.setattr(finance, "create_user_scoped_document", capture)

    finance.record_sensitive_access(user, "export", "privacy")

    assert captured["user_id"] == user.id
    assert captured["collection"] == "audit"
    assert captured["data"]["action"] == "export"
    assert captured["data"]["resource_type"] == "privacy"
    assert captured["data"]["metadata"] == {"audit_class": "sensitive_access"}
    assert "amount" not in captured["data"]
    assert "description" not in captured["data"]


def test_sensitive_access_audit_fails_closed(monkeypatch) -> None:
    user = _user()
    monkeypatch.setattr(
        finance,
        "_connection",
        lambda: (_ for _ in ()).throw(RuntimeError("storage unavailable")),
    )

    with pytest.raises(finance.FinanceAuditError):
        finance.record_sensitive_access(user, "read", "transactions")
