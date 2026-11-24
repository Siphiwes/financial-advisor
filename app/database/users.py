"""Cloudant persistence for application user accounts."""

from datetime import UTC, datetime
from uuid import uuid4

from app.core.security import (
    get_email_lookup_document_id,
    hash_password,
    verify_password,
)


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



class InvalidCurrentPasswordError(ValueError):
    """Raised when password re-verification fails."""


def change_user_password(
    client,
    database: str,
    email: str,
    user_id: str,
    current_password: str,
    new_password: str,
) -> dict:
    """Replace a password hash and invalidate all previously issued tokens."""
    user_document = get_user_by_email(client, database, email)
    if (
        not user_document
        or user_document.get("type") != "user"
        or user_document.get("user_id") != user_id
        or user_document.get("is_active") is not True
        or not user_document.get("password_hash")
        or not verify_password(current_password, user_document["password_hash"])
    ):
        raise InvalidCurrentPasswordError("The current password is incorrect.")

    if verify_password(new_password, user_document["password_hash"]):
        raise ValueError("Choose a new password that is different from the current password.")

    updated = dict(user_document)
    updated["password_hash"] = hash_password(new_password)
    updated["auth_version"] = int(user_document.get("auth_version", 1)) + 1
    updated["updated_at"] = datetime.now(UTC).isoformat()

    result = client.put_document(
        db=database,
        doc_id=updated["_id"],
        document=updated,
    ).get_result()
    if result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm the password update.")

    updated["_rev"] = result.get("rev")
    return updated


def revoke_user_sessions(
    client,
    database: str,
    email: str,
    user_id: str,
    current_password: str,
) -> dict:
    """Increment the auth version so every previously issued access token fails."""
    user_document = get_user_by_email(client, database, email)
    if (
        not user_document
        or user_document.get("type") != "user"
        or user_document.get("user_id") != user_id
        or user_document.get("is_active") is not True
        or not user_document.get("password_hash")
        or not verify_password(current_password, user_document["password_hash"])
    ):
        raise InvalidCurrentPasswordError("The current password is incorrect.")

    updated = dict(user_document)
    updated["auth_version"] = int(user_document.get("auth_version", 1)) + 1
    updated["updated_at"] = datetime.now(UTC).isoformat()

    result = client.put_document(
        db=database,
        doc_id=updated["_id"],
        document=updated,
    ).get_result()
    if result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm session revocation.")

    updated["_rev"] = result.get("rev")
    return updated


class InvalidActionTokenError(ValueError):
    """Raised when an account verification or password reset token is invalid."""


def _action_token_digest(raw_token: str) -> str:
    """Create a keyed digest so raw action tokens are never stored in Cloudant."""
    import hashlib
    import hmac

    from app.core.config import get_setting

    key = get_setting("AUTH_EMAIL_INDEX_KEY")
    if not key or len(key.encode("utf-8")) < 32:
        raise ValueError("The account action-token key is not configured.")
    return hmac.new(key.encode("utf-8"), raw_token.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_account_action_token(
    client,
    database: str,
    *,
    email: str,
    user_id: str,
    action: str,
    expires_minutes: int,
) -> str:
    """Create a one-time, expiring token and persist only its keyed digest."""
    import secrets
    from datetime import timedelta

    if action not in {"verify_email", "password_reset"}:
        raise ValueError("Unsupported account action.")
    raw_token = secrets.token_urlsafe(32)
    digest = _action_token_digest(raw_token)
    document_id = f"account-action:{action}:{digest}"
    now = datetime.now(UTC)
    document = {
        "_id": document_id,
        "type": "account_action",
        "action": action,
        "user_id": user_id,
        "email": email.strip().casefold(),
        "expires_at": (now + timedelta(minutes=expires_minutes)).isoformat(),
        "used": False,
        "created_at": now.isoformat(),
    }
    result = client.put_document(db=database, doc_id=document_id, document=document).get_result()
    if result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm account action-token creation.")
    return raw_token


def consume_account_action_token(
    client,
    database: str,
    *,
    raw_token: str,
    expected_action: str,
) -> dict:
    """Validate expiry and consume a token using Cloudant revision conflict protection."""
    document_id = f"account-action:{expected_action}:{_action_token_digest(raw_token)}"
    try:
        document = client.get_document(db=database, doc_id=document_id).get_result()
    except Exception as exc:
        if _has_http_status(exc, 404):
            raise InvalidActionTokenError("The link is invalid or has expired.") from exc
        raise

    now = datetime.now(UTC)
    try:
        expires_at = datetime.fromisoformat(document["expires_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidActionTokenError("The link is invalid or has expired.") from exc
    if (
        document.get("type") != "account_action"
        or document.get("action") != expected_action
        or document.get("used") is not False
        or expires_at <= now
    ):
        raise InvalidActionTokenError("The link is invalid or has expired.")

    consumed = dict(document)
    consumed["used"] = True
    consumed["used_at"] = now.isoformat()
    try:
        result = client.put_document(
            db=database,
            doc_id=document_id,
            document=consumed,
        ).get_result()
    except Exception as exc:
        if _has_http_status(exc, 409):
            raise InvalidActionTokenError("The link has already been used.") from exc
        raise
    if result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm account action-token use.")
    consumed["_rev"] = result.get("rev")
    return consumed


def verify_user_email(client, database: str, user_id: str, email: str) -> dict:
    """Mark the matching account email as verified."""
    user_document = get_user_by_email(client, database, email)
    if (
        not user_document
        or user_document.get("type") != "user"
        or user_document.get("user_id") != user_id
        or user_document.get("is_active") is not True
    ):
        raise InvalidActionTokenError("The account could not be verified.")
    if user_document.get("email_verified") is True:
        return user_document
    updated = dict(user_document)
    updated["email_verified"] = True
    updated["email_verified_at"] = datetime.now(UTC).isoformat()
    updated["updated_at"] = datetime.now(UTC).isoformat()
    result = client.put_document(db=database, doc_id=updated["_id"], document=updated).get_result()
    if result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm email verification.")
    updated["_rev"] = result.get("rev")
    return updated


def reset_user_password(
    client,
    database: str,
    *,
    user_id: str,
    email: str,
    new_password: str,
) -> dict:
    """Set a new password and invalidate every access token already issued."""
    user_document = get_user_by_email(client, database, email)
    if (
        not user_document
        or user_document.get("type") != "user"
        or user_document.get("user_id") != user_id
        or user_document.get("is_active") is not True
    ):
        raise InvalidActionTokenError("The account could not be recovered.")
    updated = dict(user_document)
    updated["password_hash"] = hash_password(new_password)
    updated["auth_version"] = int(user_document.get("auth_version", 1)) + 1
    updated["updated_at"] = datetime.now(UTC).isoformat()
    result = client.put_document(db=database, doc_id=updated["_id"], document=updated).get_result()
    if result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm the password reset.")
    updated["_rev"] = result.get("rev")
    return updated
