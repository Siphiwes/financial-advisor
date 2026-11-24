"""Validated authentication request and response models."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field

PasswordInput = Annotated[str, Field(min_length=12, max_length=128)]

class RegisterRequest(BaseModel):
    """New account registration payload."""

    email: EmailStr
    password: PasswordInput

class LoginRequest(BaseModel):
    """Account login payload."""

    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]

class UserPublic(BaseModel):
    """User fields safe to return to an authenticated client."""

    id: str
    email: EmailStr
    created_at: datetime

class TokenResponse(BaseModel):
    """Short-lived bearer access token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int

class AuthenticatedUser(BaseModel):
    """Identity supplied to protected application services."""

    id: str
    email: EmailStr
    created_at: datetime



class PasswordChangeRequest(BaseModel):
    """Change the signed-in user's password after verifying the current password."""

    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: PasswordInput


class SessionRevocationRequest(BaseModel):
    """Invalidate all existing bearer tokens after verifying the current password."""

    current_password: Annotated[str, Field(min_length=1, max_length=128)]



class AuthenticationActionResponse(BaseModel):
    message: str
    sessions_invalidated: bool = False


class AccountTokenRequest(BaseModel):
    token: Annotated[str, Field(min_length=32, max_length=256)]


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: Annotated[str, Field(min_length=32, max_length=256)]
    new_password: PasswordInput
