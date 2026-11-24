"""Authentication checks for statement-import preview."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.schemas.auth import AuthenticatedUser

client = TestClient(app)


def test_fnb_csv_preview_requires_authentication() -> None:
    response = client.post(
        "/imports/fnb/csv/preview",
        files={"file": ("statement.csv", b"", "text/csv")},
    )

    assert response.status_code == 401



def test_fnb_confirmation_requires_authentication() -> None:
    response = client.post(
        "/imports/fnb/csv/confirm",
        data={
            "account_id": "0123456789abcdef0123456789abcdef",
            "consent": "true",
        },
        files={"file": ("statement.csv", b"", "text/csv")},
    )

    assert response.status_code == 401


def test_fnb_confirmation_stays_disabled_by_default(monkeypatch) -> None:
    monkeypatch.setenv("FINANCIAL_DATA_ENABLED", "false")
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=str(uuid4()),
        email="owner@example.com",
        created_at=datetime.now(UTC),
    )
    try:
        response = client.post(
            "/imports/fnb/csv/confirm",
            data={
                "account_id": "0123456789abcdef0123456789abcdef",
                "consent": "true",
            },
            files={"file": ("statement.csv", b"", "text/csv")},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 503
