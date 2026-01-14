from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=8) # Match the 8-char requirement in service
    password_confirm: str
    first_name: str
    last_name: str
    middle_name: str


class UserLogin(BaseModel):
    email: str
    password: str = Field(min_length=6)


class UserUpdate(BaseModel):
    """
    Updated to include email and password as expected by UserService.update_user.
    Standardized 'second_name' to 'last_name' to match the model.
    """
    email: Optional[str] = None
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    is_active: Optional[bool] = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserBase(BaseModel):
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserResponse(UserBase):
    role_id: Optional[str] = None # Role might be null initially


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
    access_list: List[PermissionResponse] = []
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