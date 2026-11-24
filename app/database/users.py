"""Cloudant persistence for application user accounts."""

from datetime import UTC, datetime
from uuid import uuid4

from app.core.security import get_email_lookup_document_id, hash_password


class UserAlreadyExistsError(ValueError):
    """Raised when an account already exists for the normalized email."""


def _has_http_status(error: Exception, expected_status: int) -> bool:
    """Recognize HTTP status values returned by the Cloudant SDK."""
    for attribute in ("code", "status_code"):
        value = getattr(error, attribute, None)
        if value == expected_status:
            return True
    return False


def get_user_by_document_id(client, database: str, document_id: str) -> dict | None:
    """Load a user using the opaque document ID carried in a signed token."""
    if not document_id.startswith("user:email:"):
        return None

    try:
        return client.get_document(db=database, doc_id=document_id).get_result()
    except Exception as exc:
        if _has_http_status(exc, 404):
            return None
        raise


def get_user_by_email(client, database: str, email: str) -> dict | None:
    """Look up an account without putting its email address in a document ID."""
    document_id = get_email_lookup_document_id(email)
    return get_user_by_document_id(client, database, document_id)


def create_user(client, database: str, email: str, password: str) -> dict:
    """Create an account; a deterministic ID makes email uniqueness atomic."""
    normalized_email = email.strip().casefold()
    document_id = get_email_lookup_document_id(normalized_email)
    now = datetime.now(UTC).isoformat()
    user_document = {
        "_id": document_id,
        "type": "user",
        "user_id": str(uuid4()),
        "email": normalized_email,
        "password_hash": hash_password(password),
        "is_active": True,
        "auth_version": 1,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = client.put_document(
            db=database,
            doc_id=document_id,
            document=user_document,
        ).get_result()
    except Exception as exc:
        if _has_http_status(exc, 409):
            raise UserAlreadyExistsError(
                "An account already exists for this email address."
            ) from exc
        raise

    if result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm account creation.")

    user_document["_rev"] = result.get("rev")
    return user_document
