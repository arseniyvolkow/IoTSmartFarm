from fastapi import APIRouter, status, Response, Depends
from ..schemas import UserUpdate
from ..dependencies import (
    UserServiceDependency,
    CurrentUserDependency
)
from common.security import CheckAccess


router = APIRouter(prefix="/user", tags=["Users"])


@router.get("/me")
async def get_my_profile(
    user_service: UserServiceDependency, current_user: CurrentUserDependency
):
    return await user_service.get_user_by_id(current_user)


@router.get("/me")
async def update_my_profile(
    data: UserUpdate,
    user_service: UserServiceDependency,
    current_user: CurrentUserDependency,
):
    return await user_service.update_user(current_user, data)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_profile(
    current_user: CurrentUserDependency,
    user_service: UserServiceDependency,
):
    user_service.soft_delete_user(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)




# --- АДМИН ПАНЕЛЬ (/users/{id}) ---
# Жесткая защита через RBAC: CheckAccess

@router.get("/", dependencies=[Depends(CheckAccess("users", "read"))])
async def get_all_users(
    user_service: UserServiceDependency,
    skip: int = 0, 
    limit: int = 100,
):
    """
    ADMIN: Список всех пользователей.
    """
    return await user_service.get_all_users(skip, limit)

@router.get("/{user_id}", dependencies=[Depends(CheckAccess("users", "read"))])
async def get_user_by_id_admin(
    user_service: UserServiceDependency,
    user_id: str,

):
    """
    ADMIN: Просмотр любого профиля.
    """
    return await user_service.get_user_by_id(user_id)

@router.put("/{user_id}", dependencies=[Depends(CheckAccess("users", "write"))])
async def update_user_admin(
    user_service: UserServiceDependency,
    user_id: str,
    user_data: UserUpdate, # В идеале здесь должна быть UserAdminUpdate (с полями is_active и т.д.)
):
    """
    ADMIN: Обновление любого профиля (Смена email, бан, смена пароля).
    """
    return await user_service.update_user(user_id, user_data)

@router.delete("/{user_id}", dependencies=[Depends(CheckAccess("users", "delete"))])
async def delete_user_admin(
    user_service: UserServiceDependency,
    user_id: str,
):
    """
    ADMIN: Принудительное удаление пользователя.
    """
    return await user_service.soft_delete_user(user_id)
