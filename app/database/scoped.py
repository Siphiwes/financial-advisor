"""Cloudant helpers that namespace every finance record by its owner."""

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

_COLLECTION_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_RECORD_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_RESERVED_COLLECTIONS = {"user", "users", "system"}
MAX_SCOPED_PAGE_SIZE = 10_000


class UserScopedDocumentNotFoundError(LookupError):
    """Raised when a user-scoped record does not exist for the current user."""


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

    if record_id is not None and not _RECORD_PATTERN.fullmatch(record_id):
        raise ValueError("A valid record ID is required.")

    return normalized_user_id


def _document_prefix(user_id: str, collection: str) -> str:
    """Return the Cloudant ID prefix for one user's collection."""
    normalized_user_id = _validate_scope(user_id, collection)
    return f"finance:{normalized_user_id}:{collection}:"


def _document_id(user_id: str, collection: str, record_id: str) -> str:
    """Build a Cloudant ID that cannot address another user's namespace."""
    return f"{_document_prefix(user_id, collection)}{record_id}"


def _is_http_status(error: Exception, expected_status: int) -> bool:
    """Recognize a Cloudant HTTP status value."""
    return any(
        getattr(error, attribute, None) == expected_status
        for attribute in ("code", "status_code")
    )


def _is_not_found(error: Exception) -> bool:
    return _is_http_status(error, 404)


def _is_conflict(error: Exception) -> bool:
    return _is_http_status(error, 409)


def create_user_scoped_document(
    client,
    database: str,
    user_id: str,
    collection: str,
    data: dict,
    record_id: str | None = None,
) -> str:
    """Create a record in the user's namespace, optionally with a stable ID."""
    _validate_scope(user_id, collection)
    if not isinstance(data, dict):
        raise ValueError("Document data must be an object.")

    record_id = record_id or uuid4().hex
    document = {
        "_id": _document_id(user_id, collection, record_id),
        "type": collection,
        "user_id": user_id,
        "record_id": record_id,
        "data": data,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    result = client.post_document(db=database, document=document).get_result()
    if result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm record creation.")
    return record_id


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
    offset: int = 0,
) -> tuple[list[dict], bool]:
    """List records from one owner/collection ID range using Cloudant's primary index."""
    if not 1 <= limit <= MAX_SCOPED_PAGE_SIZE:
        raise ValueError("The requested page size is outside the supported range.")
    if not 0 <= offset <= MAX_SCOPED_PAGE_SIZE:
        raise ValueError("The requested offset is outside the supported range.")

    prefix = _document_prefix(user_id, collection)
    result = client.post_all_docs(
        db=database,
        include_docs=True,
        start_key=prefix,
        end_key=f"{prefix}\ufff0",
        inclusive_end=False,
        limit=limit + 1,
        skip=offset,
    ).get_result()

    documents = []
    for row in result.get("rows", []):
        document = row.get("doc")
        if (
            isinstance(document, dict)
            and document.get("user_id") == user_id
            and document.get("type") == collection
            and str(document.get("_id", "")).startswith(prefix)
        ):
            documents.append(document)

    has_more = len(documents) > limit
    return documents[:limit], has_more


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


def get_user_scoped_documents_by_ids(
    client,
    database: str,
    user_id: str,
    collection: str,
    record_ids: list[str],
) -> dict[str, dict]:
    """Fetch existing owner-scoped documents by deterministic IDs in batches."""
    _validate_scope(user_id, collection)
    found: dict[str, dict] = {}
    batch_size = 500

    for start in range(0, len(record_ids), batch_size):
        batch_ids = record_ids[start : start + batch_size]
        document_ids = [
            _document_id(user_id, collection, record_id)
            for record_id in batch_ids
        ]
        result = client.post_all_docs(
            db=database,
            keys=document_ids,
            include_docs=True,
        ).get_result()
        for row in result.get("rows", []):
            document = row.get("doc")
            if not isinstance(document, dict):
                continue
            record_id = document.get("record_id")
            if (
                record_id in batch_ids
                and document.get("user_id") == user_id
                and document.get("type") == collection
                and document.get("_id") == _document_id(user_id, collection, record_id)
            ):
                found[record_id] = document
    return found


def bulk_create_user_scoped_documents(
    client,
    database: str,
    user_id: str,
    collection: str,
    records: list[tuple[str, dict]],
) -> dict[str, int]:
    """Create deterministic owner-scoped records in bounded Cloudant bulk requests.

    Cloudant bulk writes are not transactional. A response is inspected per
    document, and any non-conflict failure raises so the caller can mark the
    enclosing import as partial and safely retry.
    """
    _validate_scope(user_id, collection)
    created_count = 0
    conflict_count = 0
    batch_size = 200

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        now = datetime.now(UTC).isoformat()
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
        if not isinstance(results, list) or len(results) != len(documents):
            raise RuntimeError("Cloudant returned an incomplete bulk-write result.")

        for result in results:
            if result.get("ok") is True or result.get("rev"):
                created_count += 1
            elif result.get("error") == "conflict":
                conflict_count += 1
            else:
                raise RuntimeError("Cloudant could not save every imported record.")

    return {"created": created_count, "conflicts": conflict_count}
