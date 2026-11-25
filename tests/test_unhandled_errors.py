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
        "detail": "Internal server error. Check application logs."
    }
    assert "Unhandled request failure method=GET path=/test-unhandled-error" in caplog.text
    assert "sensitive internal detail" in caplog.text
