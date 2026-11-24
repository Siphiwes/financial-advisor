"""Verify that deletion locks block normal requests but permit deletion retries."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api import dependencies


def test_deletion_lock_blocks_normal_requests_and_allows_retry(monkeypatch) -> None:
    user_id = str(uuid4())
    claims = {
        "sub": user_id,
        "udoc": "user:email:opaque-index",
        "ver": 4,
    }
    user_document = {
        "_id": "user:email:opaque-index",
        "type": "user",
        "user_id": user_id,
        "email": "owner@example.com",
        "is_active": True,
        "is_deleting": True,
        "auth_version": 4,
        "created_at": datetime.now(UTC).isoformat(),
    }
    monkeypatch.setattr(dependencies, "decode_access_token", lambda token: claims)
    monkeypatch.setattr(dependencies, "get_cloudant_client", lambda: object())
    monkeypatch.setattr(dependencies, "get_database_name", lambda: "finance-advisor-db")
    monkeypatch.setattr(
        dependencies,
        "get_user_by_document_id",
        lambda client, database, document_id: user_document,
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="access-token",
    )

    with pytest.raises(HTTPException) as error:
        dependencies.get_current_user(credentials)

    assert error.value.status_code == 423
    deletion_user = dependencies.get_user_for_deletion(credentials)
    assert deletion_user.id == user_id
