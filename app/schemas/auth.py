from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
import uuid


def normalise_email(email: str) -> str:
    """Emails are stored and compared in lower case: Jane@x.org is jane@x.org."""
    return email.strip().lower()


def normalise_display_name(name: str | None) -> str | None:
    """Spaces trimmed; blank means no name."""
    if name is None:
        return None
    return " ".join(name.split()) or None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=100)

    _email = field_validator("email")(normalise_email)
    _display_name = field_validator("display_name")(normalise_display_name)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    _email = field_validator("email")(normalise_email)

class UpdateMeRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)

    _display_name = field_validator("display_name")(normalise_display_name)

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    # Kept for older clients.
    expires_in_hours: float

class RefreshRequest(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str | None = None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    deleted_at: datetime | None

class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

class PermissionOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)

class UserLookupRequest(BaseModel):
    ids: list[uuid.UUID] = Field(max_length=1000)


class UserSummary(BaseModel):
    """How another service shows a user."""
    id: uuid.UUID
    email: str
    display_name: str | None
