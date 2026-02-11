from pydantic import BaseModel
import uuid

class CreateRole(BaseModel):
    name: str
    description: str | None = None

class CreatePermission(BaseModel):
    name: str
    description: str | None = None

class AssignRole(BaseModel):
    role_name: str

class AssignPermissionToRole(BaseModel):
    permission_name: str
