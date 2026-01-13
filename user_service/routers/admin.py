from fastapi import APIRouter, status, Depends
from user_service.schemas import RoleResponse, RoleCreate, PermissionSet
from user_service.dependencies import RBACServiceDependency
from common.security import CheckAccess
from typing import List

router = APIRouter(prefix="/admin/roles", tags=["Admin"])


@router.get(
    "/",
    response_model=List[RoleResponse],
    dependencies=[Depends(CheckAccess("roles", "read"))],
)
async def get_all_roles(rbac_service: RBACServiceDependency):
    """Список всех доступных ролей с их правами."""
    return await rbac_service.get_all_roles()


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=RoleResponse,
    dependencies=[Depends(CheckAccess("roles", "write"))],
)
async def create_new_role(
    role_data: RoleCreate,
    rbac_service: RBACServiceDependency,
):
    """Создание новой роли."""
    return await rbac_service.create_role(
        name=role_data.name,
        can_read_all=role_data.can_read_all,
        can_write_all=role_data.can_write_all,
    )


@router.post(
    "/{role_name}/permissions",
    response_model=RoleResponse,
    dependencies=[Depends(CheckAccess("roles", "write"))],
)
async def set_permission_for_role(
    role_name: str, perm_data: PermissionSet, rbac_service: RBACServiceDependency
):
    """
    Добавить или обновить права роли для конкретного ресурса (UPSERT).
    """
    return await rbac_service.set_role_access(
        role_name=role_name,
        resource=perm_data.resource,
        can_read=perm_data.can_read,
        can_write=perm_data.can_write,
        can_delete=perm_data.can_delete,
    )


@router.get(
    "/{role_name}",
    response_model=RoleResponse,
    dependencies=[Depends(CheckAccess("roles", "read"))],
)
async def get_role_details(role_name: str, rbac_service: RBACServiceDependency):
    """Детальная информация о роли."""
    return await rbac_service.get_role_by_name(role_name)


@router.delete(
    "/{role_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(CheckAccess("roles", "delete"))],
)
async def delete_role(role_name: str, rbac_service: RBACServiceDependency):
    """Удалить роль."""
    await rbac_service.delete_role(role_name)
    return None
