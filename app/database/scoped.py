"""Cloudant helpers that namespace every finance record by its owner."""

import re
from threading import Lock
from datetime import UTC, datetime
from uuid import UUID, uuid4

_COLLECTION_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_RESERVED_COLLECTIONS = {"user", "users", "system"}
MAX_QUERY_LIMIT = 500
_INDEX_LOCK = Lock()
_INDEXED_DATABASES: set[str] = set()


class UserScopedDocumentNotFoundError(LookupError):
    """Raised when a user-scoped record does not exist for the current user."""


class UserScopedDocumentConflictError(RuntimeError):
    """Raised when a deterministic user-scoped document ID already exists."""


def _validate_scope(user_id: str, collection: str, record_id: str | None = None) -> str:
    """Validate identifiers before composing a Cloudant document ID."""
    try:
        normalized_user_id = UUID(user_id).hex
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("A valid user ID is required.") from exc

    if (
        not _COLLECTION_PATTERN.fullmatch(collection)
        or collection in _RESERVED_COLLECTIONS
    ):
        raise ValueError("The requested collection is not allowed.")

    if record_id is not None and not re.fullmatch(r"[0-9a-f]{32}", record_id):
        raise ValueError("A valid record ID is required.")

    return normalized_user_id


def _document_id(user_id: str, collection: str, record_id: str) -> str:
    """Build a Cloudant ID that cannot address another user's namespace."""
    normalized_user_id = _validate_scope(user_id, collection, record_id)
    return f"finance:{normalized_user_id}:{collection}:{record_id}"


def _http_status(error: Exception) -> int | None:
    """Read an HTTP status from SDK exceptions without exposing their contents."""
    for attribute in ("code", "status_code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    return None


def _is_not_found(error: Exception) -> bool:
    return _http_status(error) == 404


def _is_conflict(error: Exception) -> bool:
    return _http_status(error) == 409


def create_user_scoped_document(
    client,
    database: str,
    user_id: str,
    collection: str,
    data: dict,
    *,
    record_id: str | None = None,
) -> str:
    """Create a finance record inside the authenticated user's document namespace.

    Callers may supply a deterministic UUID-hex record ID for idempotent imports.
    """
    _validate_scope(user_id, collection)
    if not isinstance(data, dict):
        raise ValueError("Document data must be an object.")

    selected_record_id = record_id or uuid4().hex
    document = {
        "_id": _document_id(user_id, collection, selected_record_id),
        "type": collection,
        "user_id": user_id,
        "record_id": selected_record_id,
        "data": data,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    try:
        result = client.post_document(db=database, document=document).get_result()
    except Exception as exc:
        if _is_conflict(exc):
            raise UserScopedDocumentConflictError(
                "A record with this identifier already exists."
            ) from exc
        raise

    if result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm record creation.")
    return selected_record_id


def get_user_scoped_document(
    client,
    database: str,
    user_id: str,
    collection: str,
    record_id: str,
) -> dict | None:
    """Read a record only through the current user's document namespace."""
    document_id = _document_id(user_id, collection, record_id)
    try:
        document = client.get_document(db=database, doc_id=document_id).get_result()
    except Exception as exc:
        if _is_not_found(exc):
            return None
        raise

    if (
        document.get("user_id") != user_id
        or document.get("type") != collection
        or document.get("record_id") != record_id
    ):
        return None
    return document


def list_user_scoped_documents(
    client,
    database: str,
    user_id: str,
    collection: str,
    *,
    limit: int = 100,
    bookmark: str | None = None,
    filters: dict | None = None,
) -> dict:
    """List only documents belonging to one user and one application collection."""
    _validate_scope(user_id, collection)
    if not 1 <= limit <= MAX_QUERY_LIMIT:
        raise ValueError(f"Query limit must be between 1 and {MAX_QUERY_LIMIT}.")

    selector = {"user_id": user_id, "type": collection}
    if filters:
        if {"user_id", "type", "_id"}.intersection(filters):
            raise ValueError("Query filters cannot override document ownership.")
        selector.update(filters)

    ensure_user_scope_indexes(client, database)
    result = client.post_find(
        db=database,
        selector=selector,
        limit=limit,
        bookmark=bookmark,
    ).get_result()

    documents = [
        document
        for document in result.get("docs", [])
        if (
            document.get("user_id") == user_id
            and document.get("type") == collection
        )
    ]
    return {
        "documents": documents,
        "bookmark": result.get("bookmark"),
    }


def update_user_scoped_document(
    client,
    database: str,
    user_id: str,
    collection: str,
    record_id: str,
    data: dict,
) -> dict:
    """Replace a record's data only after verifying its owner."""
    if not isinstance(data, dict):
        raise ValueError("Document data must be an object.")
    document = get_user_scoped_document(
        client,
        database,
        user_id,
        collection,
        record_id,
    )
    if document is None:
        raise UserScopedDocumentNotFoundError("The requested record was not found.")

    document["data"] = data
    document["updated_at"] = datetime.now(UTC).isoformat()
    return client.put_document(
        db=database,
        doc_id=document["_id"],
        document=document,
    ).get_result()


def delete_user_scoped_document(
    client,
    database: str,
    user_id: str,
    collection: str,
    record_id: str,
) -> bool:
    """Delete a record only after verifying its owner."""
    document = get_user_scoped_document(
        client,
        database,
        user_id,
        collection,
        record_id,
    )
    if document is None:
        raise UserScopedDocumentNotFoundError("The requested record was not found.")

    result = client.delete_document(
        db=database,
        doc_id=document["_id"],
        rev=document["_rev"],
    ).get_result()
    return result.get("ok") is True


def bulk_create_user_scoped_documents(
    client,
    database: str,
    user_id: str,
    collection: str,
    records: list[tuple[str, dict]],
) -> dict[str, int]:
    """Create deterministic user-scoped records in Cloudant bulk batches."""
    normalized_user_id = _validate_scope(user_id, collection)
    now = datetime.now(UTC).isoformat()
    created_count = 0
    conflict_count = 0
    batch_size = 200

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        documents = []
        for record_id, data in batch:
            if not isinstance(data, dict):
                raise ValueError("Document data must be an object.")
            documents.append(
                {
                    "_id": _document_id(user_id, collection, record_id),
                    "type": collection,
                    "user_id": user_id,
                    "record_id": record_id,
                    "data": data,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        results = client.post_bulk_docs(
            db=database,
            bulk_docs={"docs": documents},
        ).get_result()
        if len(results) != len(documents):
            raise RuntimeError("Cloudant returned an incomplete bulk-write result.")

        for result in results:
            if result.get("ok") is True or result.get("rev"):
                created_count += 1
            elif result.get("error") == "conflict":
                conflict_count += 1
            else:
                raise RuntimeError("Cloudant could not save every imported record.")

    return {"created": created_count, "conflicts": conflict_count}


def ensure_user_scope_indexes(client, database: str) -> None:
    """Create indexes for common owner-scoped collection and transaction queries."""
    with _INDEX_LOCK:
        if database in _INDEXED_DATABASES:
            return

        indexes = (
            ("by_user_type", ["user_id", "type"]),
            ("by_transaction_date", ["user_id", "type", "data.transaction_date"]),
            ("by_transaction_account", ["user_id", "type", "data.account_id"]),
            ("by_transaction_category", ["user_id", "type", "data.category_id"]),
            ("by_transaction_import", ["user_id", "type", "data.import_id"]),
        )
        for name, fields in indexes:
            client.post_index(
                db=database,
                ddoc="finance_user_scope",
                name=name,
                type="json",
                index={"fields": fields},
                partitioned=False,
            ).get_result()
        _INDEXED_DATABASES.add(database)
