from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import uuid

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_hours: int

class RefreshRequest(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
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