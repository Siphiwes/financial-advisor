"""Security tests for user-scoped Cloudant records using non-financial markers."""

from uuid import uuid4

import pytest

from app.database.scoped import (
    UserScopedDocumentNotFoundError,
    create_user_scoped_document,
    delete_user_scoped_document,
    get_user_scoped_document,
    list_user_scoped_documents,
    update_user_scoped_document,
)


class FakeResponse:
    def __init__(self, result):
        self.result = result

    def get_result(self):
        return self.result


class FakeCloudantClient:
    def __init__(self):
        self.documents = {}
        self.index_names = set()

    def post_document(self, *, db, document):
        self.documents[document["_id"]] = {**document, "_rev": "1-test"}
        return FakeResponse({"ok": True, "id": document["_id"], "rev": "1-test"})

    def get_document(self, *, db, doc_id):
        if doc_id not in self.documents:
            error = RuntimeError("not found")
            error.code = 404
            raise error
        return FakeResponse(dict(self.documents[doc_id]))

    def put_document(self, *, db, doc_id, document):
        updated = {**document, "_rev": "2-test"}
        self.documents[doc_id] = updated
        return FakeResponse({"ok": True, "id": doc_id, "rev": "2-test"})

    def delete_document(self, *, db, doc_id, rev):
        assert self.documents[doc_id]["_rev"] == rev
        del self.documents[doc_id]
        return FakeResponse({"ok": True, "id": doc_id, "rev": "deleted-test"})

    def post_index(self, *, db, ddoc, name, type, index):
        self.index_names.add(name)
        return FakeResponse({"result": "created"})

    def post_find(self, *, db, selector, limit, bookmark=None):
        matches = []
        for document in self.documents.values():
            if all(document.get(field) == expected for field, expected in selector.items()):
                matches.append(dict(document))
        return FakeResponse({"docs": matches[:limit], "bookmark": None})


@pytest.fixture
def client():
    return FakeCloudantClient()


def test_user_can_create_and_read_own_document(client):
    user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client,
        "finance-advisor-db",
        user_id,
        "transactions",
        {"ownership_check": "owner-record"},
    )

    document = get_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", record_id
    )

    assert document is not None
    assert document["user_id"] == user_id
    assert document["data"] == {"ownership_check": "owner-record"}


def test_another_user_cannot_read_document(client):
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        {"ownership_check": "owner-record"},
    )

    assert (
        get_user_scoped_document(
            client, "finance-advisor-db", other_user_id, "transactions", record_id
        )
        is None
    )


def test_another_user_cannot_update_document(client):
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        {"ownership_check": "owner-record"},
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
    assert owner_document["data"] == {"ownership_check": "owner-record"}


def test_another_user_cannot_delete_document(client):
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        {"ownership_check": "owner-record"},
    )

    with pytest.raises(UserScopedDocumentNotFoundError):
        delete_user_scoped_document(
            client, "finance-advisor-db", other_user_id, "transactions", record_id
        )

    assert get_user_scoped_document(
        client, "finance-advisor-db", owner_id, "transactions", record_id
    ) is not None


def test_owner_can_update_and_delete_document(client):
    user_id = str(uuid4())
    record_id = create_user_scoped_document(
        client,
        "finance-advisor-db",
        user_id,
        "transactions",
        {"ownership_check": "owner-record"},
    )

    update_user_scoped_document(
        client,
        "finance-advisor-db",
        user_id,
        "transactions",
        record_id,
        {"ownership_check": "owner-updated"},
    )
    updated = get_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", record_id
    )

    assert updated["data"] == {"ownership_check": "owner-updated"}
    assert delete_user_scoped_document(
        client, "finance-advisor-db", user_id, "transactions", record_id
    )
    assert (
        get_user_scoped_document(
            client, "finance-advisor-db", user_id, "transactions", record_id
        )
        is None
    )


def test_list_query_is_scoped_to_authenticated_user(client):
    owner_id = str(uuid4())
    other_user_id = str(uuid4())

    create_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "categories",
        {"ownership_check": "owner-category"},
    )
    create_user_scoped_document(
        client,
        "finance-advisor-db",
        other_user_id,
        "categories",
        {"ownership_check": "other-user-category"},
    )

    result = list_user_scoped_documents(
        client, "finance-advisor-db", owner_id, "categories"
    )

    assert len(result["documents"]) == 1
    assert result["documents"][0]["user_id"] == owner_id
    assert "by_user_type" in client.index_names


def test_query_filters_cannot_override_ownership(client):
    with pytest.raises(ValueError, match="cannot override"):
        list_user_scoped_documents(
            client,
            "finance-advisor-db",
            str(uuid4()),
            "categories",
            filters={"user_id": str(uuid4())},
        )


def test_reserved_collection_is_rejected(client):
    with pytest.raises(ValueError, match="collection is not allowed"):
        create_user_scoped_document(
            client,
            "finance-advisor-db",
            str(uuid4()),
            "users",
            {"ownership_check": "reserved"},
        )
