from pydantic import BaseModel, ConfigDict, Field
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
    role_id: str


class PermissionBase(BaseModel):
    resource: str
    can_read: bool = False
    can_write: bool = False
    can_delete: bool = False

class PermissionSet(PermissionBase):
    """Для входящих данных при создании/обновлении прав"""
    pass

class PermissionResponse(PermissionBase):
    """Для отображения прав внутри RoleResponse"""
    id: str  # В модели RoleAccess это String (UUID)
    
    model_config = ConfigDict(from_attributes=True)

class RoleBase(BaseModel):
    name: str
    can_read_all: bool = False
    can_write_all: bool = False

class RoleCreate(RoleBase):
    pass

class RoleResponse(RoleBase):
    id: str  # В модели Role это String (UUID)
    # Поле называется access_list, как relationship в модели Role
    access_list: List[PermissionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AccessRoleRuleBase(BaseModel):
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
