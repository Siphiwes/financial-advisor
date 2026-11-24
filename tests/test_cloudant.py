from app.database.cloudant import verify_document_round_trip


class FakeResponse:
    def __init__(self, result: dict) -> None:
        self.result = result

    def get_result(self) -> dict:
        return self.result


class FakeCloudantClient:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}
        self.deleted = False

    def post_document(self, *, db: str, document: dict) -> FakeResponse:
        assert db == "finance-advisor-db"
        document_id = "diagnostic-id"
        self.documents[document_id] = {**document, "_id": document_id, "_rev": "1-test"}
        return FakeResponse({"ok": True, "id": document_id, "rev": "1-test"})

    def get_document(self, *, db: str, doc_id: str) -> FakeResponse:
        assert db == "finance-advisor-db"
        return FakeResponse(self.documents[doc_id])

    def delete_document(self, *, db: str, doc_id: str, rev: str) -> FakeResponse:
        assert db == "finance-advisor-db"
        assert rev == self.documents[doc_id]["_rev"]
        del self.documents[doc_id]
        self.deleted = True
        return FakeResponse({"ok": True, "id": doc_id, "rev": "2-test"})


def test_document_round_trip_creates_reads_and_deletes_probe() -> None:
    fake_client = FakeCloudantClient()

    result = verify_document_round_trip(fake_client, "finance-advisor-db")  # type: ignore[arg-type]

    assert result == {"create": True, "read": True, "delete": True}
    assert fake_client.documents == {}
    assert fake_client.deleted is True
