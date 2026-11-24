"""Tests for per-user Cloudant document isolation."""

from uuid import uuid4

import pytest

from app.database.scoped import (
    UserScopedDocumentNotFoundError,
    bulk_create_user_scoped_documents,
    create_user_scoped_document,
    delete_user_scoped_document,
    get_user_scoped_document,
    get_user_scoped_documents_by_ids,
    list_user_scoped_documents,
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

    def post_all_docs(self, *, db: str, **parameters) -> FakeResponse:
        assert db == "finance-advisor-db"
        keys = parameters.get("keys")
        if keys is not None:
            rows = []
            for document_id in keys:
                document = self.documents.get(document_id)
                if document is None:
                    rows.append({"key": document_id, "error": "not_found"})
                else:
                    rows.append({"key": document_id, "doc": dict(document)})
            return FakeResponse({"rows": rows})

        prefix = parameters["start_key"]
        documents = [
            document
            for document_id, document in sorted(self.documents.items())
            if document_id.startswith(prefix)
        ]
        start = parameters.get("skip", 0)
        limit = parameters.get("limit", len(documents))
        page = documents[start : start + limit]
        return FakeResponse({"rows": [{"doc": document} for document in page]})

    def post_bulk_docs(self, *, db: str, bulk_docs: dict) -> FakeResponse:
        assert db == "finance-advisor-db"
        results = []
        for document in bulk_docs["docs"]:
            document_id = document["_id"]
            if document_id in self.documents:
                results.append({"id": document_id, "error": "conflict"})
            else:
                stored = {**document, "_rev": "1-test"}
                self.documents[document_id] = stored
                results.append({"id": document_id, "rev": "1-test", "ok": True})
        return FakeResponse(results)


@pytest.fixture
def client() -> FakeCloudantClient:
    return FakeCloudantClient()


def test_user_can_create_and_read_own_document(client: FakeCloudantClient) -> None:
    user_id = str(uuid4())

    record_id = create_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", {"ownership_check": "owner-record"}
    )
    document = get_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", record_id
    )

    assert document is not None
    assert document["user_id"] == user_id
    assert document["data"] == {"ownership_check": "owner-record"}


def test_another_user_cannot_read_document(client: FakeCloudantClient) -> None:
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client, "finance-advisor-db", owner_id, "transactions", {"ownership_check": "owner-record"}
    )

    document = get_user_scoped_document(
        client, "finance-advisor-db", other_user_id, "transactions", record_id
    )

    assert document is None


def test_another_user_cannot_update_document(client: FakeCloudantClient) -> None:
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client, "finance-advisor-db", owner_id, "transactions", {"ownership_check": "owner-record"}
    )

    with pytest.raises(UserScopedDocumentNotFoundError):
        update_user_scoped_document(
            client,
            "finance-advisor-db",
            other_user_id,
            "transactions",
            record_id,
            {"ownership_check": "other-user-attempt"},
        )

    owner_document = get_user_scoped_document(
        client, "finance-advisor-db", owner_id, "transactions", record_id
    )
    assert owner_document is not None
    assert owner_document["data"] == {"ownership_check": "owner-record"}


def test_another_user_cannot_delete_document(client: FakeCloudantClient) -> None:
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client, "finance-advisor-db", owner_id, "transactions", {"ownership_check": "owner-record"}
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
        client, "finance-advisor-db", user_id, "transactions", {"ownership_check": "owner-record"}
    )

    update_user_scoped_document(
        client,
        "finance-advisor-db",
        user_id,
        "transactions",
        record_id,
        {"ownership_check": "owner-updated-record"},
    )
    updated = get_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", record_id
    )

    assert updated is not None
    assert updated["data"] == {"ownership_check": "owner-updated-record"}
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



def test_scoped_list_only_returns_owner_collection_and_reports_more(
    client: FakeCloudantClient,
) -> None:
    owner_id = str(uuid4())
    another_user_id = str(uuid4())

    create_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        {"ownership_check": "owner-first"},
    )
    create_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        {"ownership_check": "owner-second"},
    )
    create_user_scoped_document(
        client,
        "finance-advisor-db",
        another_user_id,
        "transactions",
        {"ownership_check": "other-owner"},
    )
    create_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "budgets",
        {"ownership_check": "other-collection"},
    )

    first_page, first_has_more = list_user_scoped_documents(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        limit=1,
    )
    second_page, second_has_more = list_user_scoped_documents(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        limit=1,
        offset=1,
    )

    assert len(first_page) == 1
    assert first_has_more is True
    assert len(second_page) == 1
    assert second_has_more is False
    assert {
        first_page[0]["data"]["ownership_check"],
        second_page[0]["data"]["ownership_check"],
    } == {"owner-first", "owner-second"}



def test_bulk_lookup_returns_only_requested_owned_documents(client: FakeCloudantClient) -> None:
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    owner_record_id = create_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        {"ownership_check": "owner-record"},
    )
    create_user_scoped_document(
        client,
        "finance-advisor-db",
        other_user_id,
        "transactions",
        {"ownership_check": "other-user-record"},
    )

    result = get_user_scoped_documents_by_ids(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        [owner_record_id, "ffffffffffffffffffffffffffffffff"],
    )

    assert list(result) == [owner_record_id]
    assert result[owner_record_id]["user_id"] == owner_id


def test_bulk_create_is_batched_and_reports_conflicts(client: FakeCloudantClient) -> None:
    user_id = str(uuid4())
    records = [
        ("11111111111111111111111111111111", {"ownership_check": "first-record"}),
        ("22222222222222222222222222222222", {"ownership_check": "second-record"}),
    ]

    first = bulk_create_user_scoped_documents(
        client, "finance-advisor-db", user_id, "transactions", records
    )
    retry = bulk_create_user_scoped_documents(
        client, "finance-advisor-db", user_id, "transactions", records
    )

    assert first == {"created": 2, "conflicts": 0}
    assert retry == {"created": 0, "conflicts": 2}
    assert len(client.documents) == 2
