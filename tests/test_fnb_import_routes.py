"""Authentication checks for statement-import preview."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_fnb_csv_preview_requires_authentication() -> None:
    response = client.post(
        "/imports/fnb/csv/preview",
        files={"file": ("statement.csv", b"", "text/csv")},
    )

    assert response.status_code == 401
