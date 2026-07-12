from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import validate_password_strength
from app.models.user import UserRole


class UserCreate(BaseModel):
    """Schema for registering a new user."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    username: str | None = Field(default=None, min_length=2, max_length=255)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        """Call the centralized security helper to validate password strength."""
        try:
            validate_password_strength(v)
        except ValueError as exc:
            raise ValueError(str(exc))
        return v


class UserUpdate(BaseModel):
    """Schema for updating user details."""

    username: str | None = Field(default=None, min_length=2, max_length=255)

    model_config = ConfigDict(str_strip_whitespace=True)


class UserResponse(BaseModel):
    """Schema for returning user details."""

    id: int
    email: EmailStr
    username: str | None
    role: UserRole
    is_active: bool
    last_login: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Schema for returning OAuth2 tokens."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Schema for decoding token payload data."""

    email: str | None = None
