import logging

from fastapi.testclient import TestClient

from app.main import create_app


def test_unhandled_exception_is_logged_and_returns_safe_response(caplog) -> None:
    application = create_app()

    @application.get("/test-unhandled-error")
    def trigger_unhandled_error() -> None:
        raise RuntimeError("sensitive internal detail")

    client = TestClient(application, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR):
        response = client.get("/test-unhandled-error")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Problem found on Server connection. Issue caused by API GET /test-unhandled-error. The server could not complete this operation."
    }
    assert response.json()["error"]["category"] == "server_error"
    assert response.json()["error"]["endpoint"] == "/test-unhandled-error"
    assert response.json()["error"]["diagnostic_id"]
    assert "Unhandled request failure" in caplog.text
    assert "sensitive internal detail" in caplog.text
