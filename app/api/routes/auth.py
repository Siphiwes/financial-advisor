"""Invite-only account registration and bearer-token authentication."""

import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.dependencies import get_current_user
from app.core.config import get_setting
from app.core.security import (
    SecurityConfigurationError,
    create_access_token,
    get_access_token_expiry_seconds,
    verify_dummy_password,
    verify_password,
)
from app.database.cloudant import (
    CloudantConfigurationError,
    get_cloudant_client,
    get_database_name,
)
from app.database.users import (
    InvalidCurrentPasswordError,
    UserAlreadyExistsError,
    change_user_password,
    create_user,
    get_user_by_email,
    revoke_user_sessions,
)
from app.schemas.auth import (
    AuthenticatedUser,
    AuthenticationActionResponse,
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    SessionRevocationRequest,
    TokenResponse,
    UserPublic,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


def _public_user(user_document: dict) -> UserPublic:
    """Project a stored user document onto the safe public response model."""
    return UserPublic(
        id=user_document["user_id"],
        email=user_document["email"],
        created_at=user_document["created_at"],
    )


def _cloudant_connection():
    """Return the configured Cloudant client and database for auth operations."""
    try:
        return get_cloudant_client(), get_database_name()
    except CloudantConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cloudant is not configured.",
        ) from exc


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register an account using an invitation code",
)
def register(
    payload: RegisterRequest,
    invitation_code: Annotated[
        str | None,
        Header(alias="X-Registration-Invite"),
    ] = None,
) -> UserPublic:
    """Create an account only when a separately stored invitation code is valid."""
    expected_code = get_setting("REGISTRATION_INVITE_CODE")
    if not expected_code:
        raise HTTPException(
            status_code=503,
            detail="Account registration is disabled until configured.",
        )
    if len(expected_code.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=503,
            detail="Account registration is not securely configured.",
        )
    if not invitation_code or not hmac.compare_digest(invitation_code, expected_code):
        raise HTTPException(status_code=403, detail="A valid invitation is required.")

    client, database = _cloudant_connection()
    try:
        user_document = create_user(
            client,
            database,
            str(payload.email),
            payload.password,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail="An account already exists for this email address.",
        ) from exc
    except SecurityConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Account registration is not configured.",
        ) from exc
    except Exception as exc:
        logger.warning("Account registration failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Account registration could not be completed.",
        ) from exc

    return _public_user(user_document)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Exchange account credentials for an access token",
)
def issue_token(payload: LoginRequest) -> TokenResponse:
    """Authenticate an account and issue a short-lived signed bearer token."""
    client, database = _cloudant_connection()
    try:
        user_document = get_user_by_email(client, database, str(payload.email))
        stored_hash = (
            user_document.get("password_hash")
            if user_document
            else None
        )
        password_matches = (
            verify_password(payload.password, stored_hash)
            if stored_hash
            else False
        )
        if not user_document:
            verify_dummy_password(payload.password)

        if (
            not user_document
            or user_document.get("is_active") is not True
            or not password_matches
        ):
            raise HTTPException(
                status_code=401,
                detail="Email or password is incorrect.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token(
            user_id=user_document["user_id"],
            user_document_id=user_document["_id"],
            auth_version=user_document.get("auth_version", 1),
        )
        return TokenResponse(
            access_token=token,
            expires_in=get_access_token_expiry_seconds(),
        )
    except HTTPException:
        raise
    except SecurityConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured.",
        ) from exc
    except Exception as exc:
        logger.warning("Account login failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Authentication could not be completed.",
        ) from exc


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get the authenticated account",
)
def read_current_user(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> UserPublic:
    """Return the current account without exposing password or storage metadata."""
    return UserPublic(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
    )



@router.post(
    "/password/change",
    response_model=AuthenticationActionResponse,
    summary="Change the account password and invalidate existing access tokens",
)
def change_password(
    payload: PasswordChangeRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticationActionResponse:
    """Change the password after re-verifying the current password."""
    client, database = _cloudant_connection()
    try:
        change_user_password(
            client,
            database,
            current_user.email,
            current_user.id,
            payload.current_password,
            payload.new_password,
        )
    except InvalidCurrentPasswordError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Password change failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The password could not be changed.",
        ) from exc

    return AuthenticationActionResponse(
        message="Password changed. Sign in again with the new password.",
        sessions_invalidated=True,
    )


@router.post(
    "/sessions/revoke",
    response_model=AuthenticationActionResponse,
    summary="Sign out all sessions by invalidating previously issued access tokens",
)
def revoke_sessions(
    payload: SessionRevocationRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticationActionResponse:
    """Invalidate all current bearer tokens after password re-verification."""
    client, database = _cloudant_connection()
    try:
        revoke_user_sessions(
            client,
            database,
            current_user.email,
            current_user.id,
            payload.current_password,
        )
    except InvalidCurrentPasswordError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Session revocation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The account sessions could not be revoked.",
        ) from exc

    return AuthenticationActionResponse(
        message="All previously issued access tokens have been invalidated.",
        sessions_invalidated=True,
    )
