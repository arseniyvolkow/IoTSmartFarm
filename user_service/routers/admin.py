from fastapi import APIRouter, status, Depends
from ..schemas import RoleResponse, RoleCreate, PermissionSet, PermissionResponse
from ..dependencies import RBACServiceDependency
from common.security import CheckAccess
from typing import List

router = APIRouter(prefix="/admin", tags=["Admin"])


def map_role_to_response(role) -> RoleResponse:
    """
    Хелпер для конвертации ORM модели Role в Pydantic схему RoleResponse.
    Позволяет избежать дублирования кода в эндпоинтах.
    """
    perms_dto = [
        PermissionResponse(
            resource=a.resource,
            can_read=a.can_read,
            can_write=a.can_write,
            can_delete=a.can_delete,
        )
        for a in role.access_list
    ]

    return RoleResponse(
        name=role.name,
        can_read_all=role.can_read_all,
        can_write_all=role.can_write_all,
        permissions=perms_dto,
    )


@router.get(
    "/",
    response_model=List[RoleResponse],
    dependencies=[Depends(CheckAccess("roles", "read"))],
)
async def get_all_roles(rbac_service: RBACServiceDependency):
    """
    Список всех доступных ролей.
    """
    # Вам нужно будет добавить метод get_all_roles в RBACService
    roles = await rbac_service.get_all_roles()
    return [map_role_to_response(role) for role in roles]


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

    # Создаем роль
    new_role = await rbac_service.create_role(
        name=role_data.name,
        can_read_all=role_data.can_read_all,
        can_write_all=role_data.can_write_all,
    )

    # Формируем ответ (у новой роли список прав пустой)
    return RoleResponse(
        name=new_role.name,
        can_read_all=new_role.can_read_all,
        can_write_all=new_role.can_write_all,
        permissions=[],
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
    Добавить или Обновить права роли для конкретного ресурса.
    Требует права записи в ресурс 'roles'.
    """
    updated_role = await rbac_service.set_role_access(
        role_name=role_name,
        resource=perm_data.resource,
        can_read=perm_data.can_read,
        can_write=perm_data.can_write,
        can_delete=perm_data.can_delete,
    )

    # Конвертируем ORM объекты (RoleAccess) в Pydantic (PermissionResponse)
    perms_dto = [
        PermissionResponse(
            resource=a.resource,
            can_read=a.can_read,
            can_write=a.can_write,
            can_delete=a.can_delete,
        )
        for a in updated_role.access_list
    ]

    return RoleResponse(
        name=updated_role.name,
        can_read_all=updated_role.can_read_all,
        can_write_all=updated_role.can_write_all,
        permissions=perms_dto,
    )


@router.get(
    "/{role_name}",
    response_model=RoleResponse,
    dependencies=[Depends(CheckAccess("roles", "read"))],
)
async def get_role_details(role_name: str, rbac_service: RBACServiceDependency):
    """
    Посмотреть детальную информацию о роли и всех её правах.
    Требует права чтения ресурса 'roles'.
    """
    role = await rbac_service.get_role_by_name(role_name)

    perms_dto = [
        PermissionResponse(
            resource=a.resource,
            can_read=a.can_read,
            can_write=a.can_write,
            can_delete=a.can_delete,
        )
        for a in role.access_list
    ]

    return RoleResponse(
        name=role.name,
        can_read_all=role.can_read_all,
        can_write_all=role.can_write_all,
        permissions=perms_dto,
    )


@router.delete(
    "/{role_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(CheckAccess("roles", "delete"))],
)
async def delete_role(role_name: str, rbac_service: RBACServiceDependency):
    """
    Удалить роль.
    """
    # Вам нужно будет добавить метод delete_role в RBACService
    await rbac_service.delete_role(role_name)
    return None
