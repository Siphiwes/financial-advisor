"""Invite-only account registration and bearer-token authentication."""

import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.dependencies import get_current_user
from app.core.config import get_setting
from app.core.rate_limit import (
    RateLimitExceeded,
    RateLimitUnavailable,
    enforce_rate_limit,
)
from app.integrations.email import EmailConfigurationError, EmailDeliveryError, send_account_email
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
    InvalidActionTokenError,
    InvalidCurrentPasswordError,
    UserAlreadyExistsError,
    change_user_password,
    consume_account_action_token,
    issue_account_action_token,
    create_user,
    get_user_by_email,
    revoke_user_sessions,
    reset_user_password,
    verify_user_email,
)
from app.schemas.auth import (
    AccountTokenRequest,
    AuthenticatedUser,
    AuthenticationActionResponse,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
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


def _enforce_auth_limit(action: str, identifier: str, *, limit: int, window: int) -> None:
    """Convert shared rate-limit outcomes into safe HTTP responses."""
    try:
        enforce_rate_limit(
            action,
            identifier,
            limit=limit,
            window_seconds=window,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="Too many authentication attempts. Try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except RateLimitUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication is temporarily unavailable.",
        ) from exc


def _peer_identifier(request: Request) -> str:
    """Use the socket peer, not an untrusted client-supplied forwarding header."""
    if request.client is None:
        return "unknown-peer"
    return request.client.host


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
    request: Request,
    invitation_code: Annotated[
        str | None,
        Header(alias="X-Registration-Invite"),
    ] = None,
) -> UserPublic:
    """Create an account only when a separately stored invitation code is valid."""
    _enforce_auth_limit(
        "register-peer",
        _peer_identifier(request),
        limit=10,
        window=3600,
    )
    _enforce_auth_limit(
        "register-email",
        str(payload.email),
        limit=3,
        window=3600,
    )
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

    try:
        token = issue_account_action_token(
            client, database, email=user_document["email"],
            user_id=user_document["user_id"], action="verify_email", expires_minutes=60,
        )
        public_url = (get_setting("APP_PUBLIC_URL") or "").rstrip("/")
        if not public_url.startswith("https://"):
            raise EmailConfigurationError("APP_PUBLIC_URL must be an HTTPS URL.")
        link = f"{public_url}/app?verify_token={token}"
        send_account_email(
            recipient=user_document["email"],
            subject="Verify your Financial Advisor email",
            text_body=f"Verify your email within 60 minutes: {link}",
            html_body=f'<p><a href="{link}">Verify email address</a></p><p>This link expires in 60 minutes.</p>',
        )
    except (EmailConfigurationError, EmailDeliveryError) as exc:
        logger.warning("Registration email was not sent: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Account created, but verification email could not be sent. Configure email and request a new link.") from exc
    except Exception as exc:
        logger.warning("Registration verification setup failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The verification email could not be prepared.") from exc

    return _public_user(user_document)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Exchange account credentials for an access token",
)
def issue_token(payload: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate an account and issue a short-lived signed bearer token."""
    _enforce_auth_limit(
        "login-peer",
        _peer_identifier(request),
        limit=60,
        window=900,
    )
    _enforce_auth_limit(
        "login-email",
        str(payload.email),
        limit=8,
        window=900,
    )
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


@router.post("/verify-email", response_model=AuthenticationActionResponse)
def verify_email(payload: AccountTokenRequest) -> AuthenticationActionResponse:
    """Consume a one-time verification link and verify the account email."""
    client, database = _cloudant_connection()
    try:
        action = consume_account_action_token(client, database, raw_token=payload.token, expected_action="verify_email")
        verify_user_email(client, database, action["user_id"], action["email"])
    except InvalidActionTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Email verification failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Email verification could not be completed.") from exc
    return AuthenticationActionResponse(message="Email address verified. You can now sign in.")


@router.post("/email/resend", response_model=AuthenticationActionResponse)
def resend_verification(current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> AuthenticationActionResponse:
    """Send a fresh verification link to the authenticated account."""
    client, database = _cloudant_connection()
    user = get_user_by_email(client, database, current_user.email)
    if not user or user.get("email_verified") is True:
        return AuthenticationActionResponse(message="If verification is required, a new link will be sent.")
    try:
        token = issue_account_action_token(client, database, email=current_user.email, user_id=current_user.id, action="verify_email", expires_minutes=60)
        public_url = (get_setting("APP_PUBLIC_URL") or "").rstrip("/")
        if not public_url.startswith("https://"):
            raise EmailConfigurationError("APP_PUBLIC_URL must be an HTTPS URL.")
        link = f"{public_url}/app?verify_token={token}"
        send_account_email(recipient=current_user.email, subject="Verify your Financial Advisor email", text_body=f"Verify your email within 60 minutes: {link}", html_body=f'<p><a href="{link}">Verify email address</a></p><p>This link expires in 60 minutes.</p>')
    except (EmailConfigurationError, EmailDeliveryError) as exc:
        raise HTTPException(status_code=503, detail="Verification email is not available.") from exc
    return AuthenticationActionResponse(message="A new verification link has been sent.")


@router.post("/password/reset/request", response_model=AuthenticationActionResponse)
def request_password_reset(payload: PasswordResetRequest) -> AuthenticationActionResponse:
    """Request a password reset without disclosing whether an account exists."""
    client, database = _cloudant_connection()
    try:
        user = get_user_by_email(client, database, str(payload.email))
        if user and user.get("is_active") is True:
            token = issue_account_action_token(client, database, email=user["email"], user_id=user["user_id"], action="password_reset", expires_minutes=30)
            public_url = (get_setting("APP_PUBLIC_URL") or "").rstrip("/")
            if not public_url.startswith("https://"):
                raise EmailConfigurationError("APP_PUBLIC_URL must be an HTTPS URL.")
            link = f"{public_url}/app?reset_token={token}"
            send_account_email(recipient=user["email"], subject="Reset your Financial Advisor password", text_body=f"Reset your password within 30 minutes: {link}", html_body=f'<p>Reset your password using the link below. It expires in 30 minutes.</p><p><a href="{link}">Reset password</a></p><p>If you did not request this, ignore this message.</p>')
    except (EmailConfigurationError, EmailDeliveryError) as exc:
        logger.warning("Password reset email unavailable: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Password recovery email is not configured.") from exc
    except Exception as exc:
        logger.warning("Password reset request failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The password reset request could not be completed.") from exc
    return AuthenticationActionResponse(message="If an active account matches that address, a password reset link will be sent.")


@router.post("/password/reset/confirm", response_model=AuthenticationActionResponse)
def confirm_password_reset(payload: PasswordResetConfirmRequest) -> AuthenticationActionResponse:
    """Consume a one-time reset link and replace the account password."""
    client, database = _cloudant_connection()
    try:
        action = consume_account_action_token(client, database, raw_token=payload.token, expected_action="password_reset")
        reset_user_password(client, database, user_id=action["user_id"], email=action["email"], new_password=payload.new_password)
    except InvalidActionTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Password reset failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The password could not be reset.") from exc
    return AuthenticationActionResponse(message="Password reset successfully. Sign in using your new password.", sessions_invalidated=True)
