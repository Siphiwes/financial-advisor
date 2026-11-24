"""Password hashing, email indexing and signed access-token utilities."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import get_setting

JWT_ISSUER = "financial-advisor-api"
JWT_AUDIENCE = "financial-advisor-api"
JWT_ALGORITHM = "HS256"

_password_hasher = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = _password_hasher.hash(secrets.token_urlsafe(32))

class SecurityConfigurationError(ValueError):
    """Raised when required authentication secrets or settings are invalid."""

def _required_secret(name: str, minimum_bytes: int = 32) -> str:
    """Read a secret and enforce a minimum entropy-oriented length."""
    value = get_setting(name)
    if not value:
        raise SecurityConfigurationError(f"{name} is not configured.")
    if len(value.encode("utf-8")) < minimum_bytes:
        raise SecurityConfigurationError(
            f"{name} must contain at least {minimum_bytes} bytes."
        )
    return value

def get_email_lookup_document_id(email: str) -> str:
    """Create a deterministic, non-reversible Cloudant ID for an email address."""
    key = _required_secret("AUTH_EMAIL_INDEX_KEY")
    normalized_email = email.strip().casefold()
    digest = hmac.new(
        key.encode("utf-8"),
        normalized_email.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"user:email:{digest}"

def hash_password(password: str) -> str:
    """Hash a password using the recommended Argon2 configuration."""
    return _password_hasher.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without exposing malformed stored hashes."""
    try:
        return _password_hasher.verify(password, password_hash)
    except Exception:
        return False

def verify_dummy_password(password: str) -> None:
    """Perform a password-hash operation when an account lookup finds no user."""
    verify_password(password, _DUMMY_PASSWORD_HASH)

def get_access_token_expiry_seconds() -> int:
    """Return the configured access-token lifetime, constrained to 5-60 minutes."""
    raw_minutes = get_setting("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    try:
        minutes = int(raw_minutes or "15")
    except ValueError as exc:
        raise SecurityConfigurationError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be an integer."
        ) from exc

    if not 5 <= minutes <= 60:
        raise SecurityConfigurationError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be between 5 and 60."
        )
    return minutes * 60

def _jwt_secret() -> str:
    """Return the signing secret after enforcing the supported algorithm."""
    configured_algorithm = get_setting("JWT_ALGORITHM", JWT_ALGORITHM)
    if configured_algorithm != JWT_ALGORITHM:
        raise SecurityConfigurationError("JWT_ALGORITHM must be HS256.")
    return _required_secret("JWT_SECRET_KEY")

def create_access_token(
    user_id: str,
    user_document_id: str,
    auth_version: int,
) -> str:
    """Create a short-lived JWT bound to one user document and auth version."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=get_access_token_expiry_seconds())
    claims: dict[str, Any] = {
        "sub": user_id,
        "udoc": user_document_id,
        "ver": auth_version,
        "typ": "access",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": expires_at,
        "jti": uuid4().hex,
    }
    return jwt.encode(claims, _jwt_secret(), algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> dict[str, Any] | None:
    """Validate an access token's signature, issuer, audience and required claims."""
    try:
        claims = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "jti"]},
        )
    except jwt.InvalidTokenError:
        return None

    if (
        claims.get("typ") != "access"
        or not isinstance(claims.get("sub"), str)
        or not isinstance(claims.get("udoc"), str)
        or not claims["udoc"].startswith("user:email:")
        or not isinstance(claims.get("ver"), int)
    ):
        return None
    return claims
