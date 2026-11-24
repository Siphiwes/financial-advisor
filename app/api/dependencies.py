"""Shared request dependencies for authenticated API operations."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import SecurityConfigurationError, decode_access_token
from app.database.cloudant import get_cloudant_client, get_database_name
from app.database.users import get_user_by_document_id
from app.schemas.auth import AuthenticatedUser

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser:
    """Validate the bearer token and load the active user from Cloudant."""
    unauthorized = HTTPException(
        status_code=401,
        detail="Authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        claims = decode_access_token(credentials.credentials)
    except SecurityConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured.",
        ) from exc

    if claims is None:
        raise unauthorized

    try:
        user_document = get_user_by_document_id(
            get_cloudant_client(),
            get_database_name(),
            claims["udoc"],
        )
    except Exception as exc:
        logger.warning("User authentication lookup failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="User authentication could not be completed.",
        ) from exc

    if (
        not user_document
        or user_document.get("type") != "user"
        or user_document.get("is_active") is not True
        or user_document.get("user_id") != claims["sub"]
        or user_document.get("auth_version") != claims["ver"]
    ):
        raise unauthorized

    return AuthenticatedUser(
        id=user_document["user_id"],
        email=user_document["email"],
        created_at=user_document["created_at"],
    )



def require_financial_data_enabled(
    _current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> None:
    """Authenticate first, then gate persistence until release safeguards pass."""
    enabled = (get_setting("FINANCIAL_DATA_ENABLED", "false") or "false").strip().casefold()
    if enabled not in {"1", "true", "yes", "on"}:
        raise HTTPException(
            status_code=503,
            detail="Financial data storage is disabled until release safeguards are completed.",
        )
