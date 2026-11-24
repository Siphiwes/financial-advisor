"""Cloudant helpers that namespace every finance record by its owner."""

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

_COLLECTION_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_RESERVED_COLLECTIONS = {"user", "users", "system"}

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

    if record_id is not None and not re.fullmatch(r"[0-9a-f]{32}", record_id):
        raise ValueError("A valid record ID is required.")

    return normalized_user_id

def _document_id(user_id: str, collection: str, record_id: str) -> str:
    """Build a Cloudant ID that cannot address another user's namespace."""
    normalized_user_id = _validate_scope(user_id, collection, record_id)
    return f"finance:{normalized_user_id}:{collection}:{record_id}"

def _is_not_found(error: Exception) -> bool:
    """Recognize a Cloudant HTTP 404 response."""
    return (
        getattr(error, "code", None) == 404
        or getattr(error, "status_code", None) == 404
    )

def create_user_scoped_document(
    client,
    database: str,
    user_id: str,
    collection: str,
    data: dict,
) -> str:
    """Create a finance record inside the authenticated user's document namespace."""
    _validate_scope(user_id, collection)
    if not isinstance(data, dict):
        raise ValueError("Document data must be an object.")

    record_id = uuid4().hex
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
        document = client.get_document(
            db=database,
            doc_id=document_id,
        ).get_result()
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
