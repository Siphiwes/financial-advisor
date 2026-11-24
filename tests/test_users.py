import pytest

from app.database.users import UserAlreadyExistsError, create_user, get_user_by_email


class FakeResponse:
    def __init__(self, result: dict) -> None:
        self.result = result

    def get_result(self) -> dict:
        return self.result


class FakeCloudantClient:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}

    def put_document(self, *, db: str, doc_id: str, document: dict) -> FakeResponse:
        if doc_id in self.documents:
            error = RuntimeError("conflict")
            error.code = 409
            raise error
        stored = {**document, "_rev": "1-test"}
        self.documents[doc_id] = stored
        return FakeResponse({"ok": True, "id": doc_id, "rev": "1-test"})

    def get_document(self, *, db: str, doc_id: str) -> FakeResponse:
        if doc_id not in self.documents:
            error = RuntimeError("not found")
            error.code = 404
            raise error
        return FakeResponse(self.documents[doc_id])


def test_user_creation_hashes_password_and_email_lookup_is_case_insensitive(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUTH_EMAIL_INDEX_KEY", "i" * 48)
    client = FakeCloudantClient()

    user = create_user(
        client,
        "finance-advisor-db",
        "Person@Example.com",
        "Correct horse battery staple 2026",
    )
    retrieved = get_user_by_email(client, "finance-advisor-db", "person@example.com")

    assert retrieved is not None
    assert retrieved["user_id"] == user["user_id"]
    assert retrieved["email"] == "person@example.com"
    assert retrieved["password_hash"] != "Correct horse battery staple 2026"
    assert "person@example.com" not in user["_id"]


def test_user_creation_rejects_duplicate_email(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_EMAIL_INDEX_KEY", "i" * 48)
    client = FakeCloudantClient()
    create_user(client, "finance-advisor-db", "person@example.com", "Password 123456")

    with pytest.raises(UserAlreadyExistsError):
        create_user(client, "finance-advisor-db", "PERSON@example.com", "Password 654321")
