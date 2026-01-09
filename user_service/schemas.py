from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=6)
    password_confirm: str
    first_name: str
    last_name: str
    middle_name: str


class UserLogin(BaseModel):
    email: str
    password: str = Field(min_length=6)


class UserUpdate(BaseModel):
    first_name: Optional[str]
    second_name: Optional[str]
    middle_name: Optional[str]


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserBase(BaseModel):
    id: set
    email: str
    first_name: Optional[str]
    second_name: Optional[str]
    middle_name: Optional[str]
    is_active: bool
    create_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    role_id: str


class RoleBase(BaseModel):
    name: str
    can_read_all: bool = False
    can_write_all: bool = False


class RoleCreate(RoleBase):
    pass


class PermissionSet(BaseModel):
    resource: str  # Например: "farms", "sensors", "users"
    can_read: bool = False
    can_write: bool = False
    can_delete: bool = False


class PermissionResponse(BaseModel):
    resource: str
    can_read: bool
    can_write: bool
    can_delete: bool


class RoleResponse(RoleBase):
    access_list: List[PermissionResponse]
    model_config = ConfigDict(from_attributes=True)


class AccessRoleRuleBase:
    role_id: str
    element_id: str

    # Разрешения (Permissions)
    read_permission: bool = False
    read_all_permission: bool = False
    create_permission: bool = False
    update_permission: bool = False
    update_all_permission: bool = False
    delete_permission: bool = False
    delete_all_permission: bool = False


class AccessRoleRuleCreate(AccessRoleRuleBase):
    """Схема для создания нового правила доступа (ввод)."""

    pass


class AccessRoleRuleResponse(AccessRoleRuleBase):
    """Схема для ответа с данными правила доступа."""

    id: str

    # Дополнительно можно добавить данные самой роли и элемента для удобства
    # role: RoleResponse
    # element: BusinessElementResponse

    class Config:
        from_attributes = True
