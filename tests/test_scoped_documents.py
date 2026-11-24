from uuid import uuid4

import pytest

from app.database.scoped import (
    create_user_scoped_document,
    get_user_scoped_document,
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
        self.documents[document["_id"]] = {
            **document,
            "_rev": "1-test",
        }
        return FakeResponse({"ok": True, "id": document["_id"]})


    def get_document(self, *, db: str, doc_id: str) -> FakeResponse:
        if doc_id not in self.documents:
            error = RuntimeError("not found")
            error.code = 404
            raise error
        return FakeResponse(self.documents[doc_id])


def test_scoped_document_is_only_retrievable_in_owner_namespace() -> None:
    client = FakeCloudantClient()
    owner_id = str(uuid4())
    other_user_id = str(uuid4())

    record_id = create_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        {"source": "private-record"},
    )

    owned_record = get_user_scoped_document(
        client,
        "finance-advisor-db",
        owner_id,
        "transactions",
        record_id,
    )
    other_users_record = get_user_scoped_document(
        client,
        "finance-advisor-db",
        other_user_id,
        "transactions",
        record_id,
    )

    assert owned_record is not None
    assert owned_record["data"]["source"] == "private-record"
    assert other_users_record is None


def test_scoped_document_rejects_invalid_collection() -> None:
    with pytest.raises(ValueError):
        create_user_scoped_document(
            FakeCloudantClient(),
            "finance-advisor-db",
            str(uuid4()),
            "Users",
            {},
        )
