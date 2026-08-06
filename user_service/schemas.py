import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=8) # Match the 8-char requirement in service
    password_confirm: str
    first_name: str
    last_name: str
    middle_name: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if (
            not re.search(r"[A-Z]", v)
            or not re.search(r"[a-z]", v)
            or not re.search(r"\d", v)
            or not re.search(r'[!@#$%^&*(),.?":{}|<>]', v)
        ):
            raise ValueError("Password must be at least 8 characters long and include uppercase, lowercase, digit, and special character.")
        return v


class UserLogin(BaseModel):
    email: str
    password: str = Field(min_length=6)


class UserUpdate(BaseModel):
    """
    Updated to include email and password as expected by UserService.update_user.
    Standardized 'second_name' to 'last_name' to match the model.
    """
    email: str | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    is_active: bool | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters long")
            if (
                not re.search(r"[A-Z]", v)
                or not re.search(r"[a-z]", v)
                or not re.search(r"\d", v)
                or not re.search(r'[!@#$%^&*(),.?":{}|<>]', v)
            ):
                raise ValueError("Password must be at least 8 characters long and include uppercase, lowercase, digit, and special character.")
        return v


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserBase(BaseModel):
    id: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserResponse(UserBase):
    role_id: str | None = None # Role might be null initially


class PermissionBase(BaseModel):
    resource: str
    can_read: bool = False
    can_write: bool = False
    can_delete: bool = False

class PermissionSet(PermissionBase):
    pass

class PermissionResponse(PermissionBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

class RoleBase(BaseModel):
    name: str
    can_read_all: bool = False
    can_write_all: bool = False

class RoleCreate(RoleBase):
    pass

class RoleResponse(RoleBase):
    id: str
    access_list: list[PermissionResponse] = []
    model_config = ConfigDict(from_attributes=True)


class AccessRoleRuleBase(BaseModel):
    role_id: str
    element_id: str
    read_permission: bool = False
    read_all_permission: bool = False
    create_permission: bool = False
    update_permission: bool = False
    update_all_permission: bool = False
    delete_permission: bool = False
    delete_all_permission: bool = False


class AccessRoleRuleCreate(AccessRoleRuleBase):
    pass


class AccessRoleRuleResponse(AccessRoleRuleBase):
    id: str
    model_config = ConfigDict(from_attributes=True)