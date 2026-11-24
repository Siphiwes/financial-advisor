from fastapi.testclient import TestClient

from app.api.routes import diagnostics
from app.main import app

client = TestClient(app)


def test_cloudant_diagnostics_are_disabled_without_token(monkeypatch) -> None:
    monkeypatch.delenv("CLOUDANT_DIAGNOSTICS_TOKEN", raising=False)

    response = client.post("/diagnostics/cloudant/round-trip")

    assert response.status_code == 503


def test_cloudant_diagnostics_reject_wrong_token(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDANT_DIAGNOSTICS_TOKEN", "expected-token")

    response = client.post(
        "/diagnostics/cloudant/round-trip",
        headers={"X-Cloudant-Diagnostics-Token": "wrong-token"},
    )

    assert response.status_code == 401


def test_cloudant_round_trip_returns_success(monkeypatch) -> None:
    class FakeResponse:
        def get_result(self) -> dict:
            return {"ok": True, "id": "probe-id", "rev": "1-test"}

    class FakeClient:
        def post_document(self, *, db: str, document: dict) -> FakeResponse:
            return FakeResponse()

    def fake_round_trip(client, database: str) -> dict[str, bool]:
        assert database == "finance-advisor-db"
        return {"create": True, "read": True, "delete": True}

    monkeypatch.setenv("CLOUDANT_DIAGNOSTICS_TOKEN", "expected-token")
    monkeypatch.setattr(diagnostics, "get_cloudant_client", lambda: FakeClient())
    monkeypatch.setattr(diagnostics, "get_database_name", lambda: "finance-advisor-db")
    monkeypatch.setattr(diagnostics, "verify_document_round_trip", fake_round_trip)

    response = client.post(
        "/diagnostics/cloudant/round-trip",
        headers={"X-Cloudant-Diagnostics-Token": "expected-token"},
    )

    assert response.status_code == 200
    assert response.json()["checks"] == {"create": True, "read": True, "delete": True}
