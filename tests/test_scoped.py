"""Tests for per-user Cloudant document isolation."""

from uuid import uuid4

import pytest

from app.database.scoped import (
    UserScopedDocumentNotFoundError,
    create_user_scoped_document,
    delete_user_scoped_document,
    get_user_scoped_document,
    update_user_scoped_document,
)


class FakeResponse:
    def __init__(self, result: dict) -> None:
        self.result = result

    def get_result(self) -> dict:
        return self.result


class FakeCloudantClient:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}

    def post_document(self, *, db: str, document: dict) -> FakeResponse:
        assert db == "finance-advisor-db"
        document_id = document["_id"]
        if document_id in self.documents:
            raise AssertionError("Document ID already exists.")
        stored = {**document, "_rev": "1-test"}
        self.documents[document_id] = stored
        return FakeResponse({"ok": True, "id": document_id, "rev": "1-test"})

    def get_document(self, *, db: str, doc_id: str) -> FakeResponse:
        assert db == "finance-advisor-db"
        if doc_id not in self.documents:
            error = RuntimeError("Not found")
            error.code = 404  # type: ignore[attr-defined]
            raise error
        return FakeResponse(dict(self.documents[doc_id]))

    def put_document(
        self,
        *,
        db: str,
        doc_id: str,
        document: dict,
    ) -> FakeResponse:
        assert db == "finance-advisor-db"
        assert doc_id in self.documents
        updated = {**document, "_rev": "2-test"}
        self.documents[doc_id] = updated
        return FakeResponse({"ok": True, "id": doc_id, "rev": "2-test"})

    def delete_document(self, *, db: str, doc_id: str, rev: str) -> FakeResponse:
        assert db == "finance-advisor-db"
        assert self.documents[doc_id]["_rev"] == rev
        del self.documents[doc_id]
        return FakeResponse({"ok": True, "id": doc_id, "rev": "2-test"})


@pytest.fixture
def client() -> FakeCloudantClient:
    return FakeCloudantClient()


def test_user_can_create_and_read_own_document(client: FakeCloudantClient) -> None:
    user_id = str(uuid4())

    record_id = create_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", {"amount": 125.50}
    )
    document = get_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", record_id
    )

    assert document is not None
    assert document["user_id"] == user_id
    assert document["data"] == {"amount": 125.50}


def test_another_user_cannot_read_document(client: FakeCloudantClient) -> None:
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client, "finance-advisor-db", owner_id, "transactions", {"amount": 125.50}
    )

    document = get_user_scoped_document(
        client, "finance-advisor-db", other_user_id, "transactions", record_id
    )

    assert document is None


def test_another_user_cannot_update_document(client: FakeCloudantClient) -> None:
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client, "finance-advisor-db", owner_id, "transactions", {"amount": 125.50}
    )

    with pytest.raises(UserScopedDocumentNotFoundError):
        update_user_scoped_document(
            client,
            "finance-advisor-db",
            other_user_id,
            "transactions",
            record_id,
            {"amount": 1.00},
        )

    owner_document = get_user_scoped_document(
        client, "finance-advisor-db", owner_id, "transactions", record_id
    )
    assert owner_document is not None
    assert owner_document["data"] == {"amount": 125.50}


def test_another_user_cannot_delete_document(client: FakeCloudantClient) -> None:
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client, "finance-advisor-db", owner_id, "transactions", {"amount": 125.50}
    )

    with pytest.raises(UserScopedDocumentNotFoundError):
        delete_user_scoped_document(
            client, "finance-advisor-db", other_user_id, "transactions", record_id
        )

    assert (
        get_user_scoped_document(
            client, "finance-advisor-db", owner_id, "transactions", record_id
        )
        is not None
    )


def test_owner_can_update_and_delete_document(client: FakeCloudantClient) -> None:
    user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", {"amount": 125.50}
    )

    update_user_scoped_document(
        client,
        "finance-advisor-db",
        user_id,
        "transactions",
        record_id,
        {"amount": 99.00},
    )
    updated = get_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", record_id
    )

    assert updated is not None
    assert updated["data"] == {"amount": 99.00}
    assert delete_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", record_id
    )
    assert get_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", record_id
    ) is None


def test_reserved_collection_is_rejected(client: FakeCloudantClient) -> None:
    with pytest.raises(ValueError, match="collection is not allowed"):
        create_user_scoped_document(
            client, "finance-advisor-db", str(uuid4()), "users", {"email": "private"}
        )
