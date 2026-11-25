"""Shared request dependencies for authenticated API operations."""

import logging
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_setting
from app.core.security import SecurityConfigurationError, decode_access_token
from app.database.cloudant import get_cloudant_client, get_database_name
from app.database.users import get_user_by_document_id
from app.schemas.auth import AuthenticatedUser

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


ACCESS_TOKEN_COOKIE = "finance_access_token"


def _load_authenticated_user(
    token: str | None,
    *,
    allow_deletion_in_progress: bool = False,
) -> AuthenticatedUser:
    """Validate a signed session token and resolve its active Cloudant user document."""
    unauthorized = HTTPException(
        status_code=401,
        detail="Authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise unauthorized

    try:
        claims = decode_access_token(token)
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

    if user_document.get("is_deleting") is True and not allow_deletion_in_progress:
        raise HTTPException(
            status_code=423,
            detail="Account deletion is in progress. Retry the deletion request to continue.",
        )

    return AuthenticatedUser(
        id=user_document["user_id"],
        email=user_document["email"],
        created_at=user_document["created_at"],
    )


def _request_token(
    request: Request | None,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Prefer bearer credentials, otherwise use the HttpOnly browser cookie."""
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    if request is None:
        return None

    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not cookie_token:
        return None

    # SameSite=Strict is the primary CSRF control. Validate Origin as a second
    # control for state-changing requests authenticated by the browser cookie.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = urlsplit(request.headers.get("origin") or "")
        if (
            origin.scheme != "https"
            or origin.netloc != request.url.netloc
            or origin.path not in {"", "/"}
            or origin.query
            or origin.fragment
        ):
            raise HTTPException(status_code=403, detail="The request origin is not allowed.")
    return cookie_token


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    request: Request | None = None,
) -> AuthenticatedUser:
    """Validate bearer or HttpOnly-cookie authentication."""
    return _load_authenticated_user(_request_token(request, credentials))


def get_user_for_deletion(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    request: Request | None = None,
) -> AuthenticatedUser:
    """Allow only the deletion workflow to resume an account already being deleted."""
    return _load_authenticated_user(
        _request_token(request, credentials),
        allow_deletion_in_progress=True,
    )


def require_financial_data_enabled(
    _current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> None:
    """Authenticate first, then gate persistence until release safeguards pass."""
    enabled = (get_setting("FINANCIAL_DATA_ENABLED", "true") or "true").strip().casefold()
    if enabled not in {"1", "true", "yes", "on"}:
        raise HTTPException(
            status_code=503,
            detail="Financial data storage is disabled until release safeguards are completed.",
        )


def require_financial_ai_enabled(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_financial_data_enabled),
    ],
) -> None:
    """Require the finance feature gate and a separate AI feature switch."""
    enabled = (
        get_setting("FINANCIAL_AI_ENABLED", "false") or "false"
    ).strip().casefold()
    if enabled not in {"1", "true", "yes", "on"}:
        raise HTTPException(
            status_code=503,
            detail="The AI financial advisor is not enabled.",
        )
