from fastapi import APIRouter, status, Response, Depends
from user_service.schemas import UserUpdate, UserResponse
from user_service.dependencies import UserServiceDependency, CurrentUserDependency
from common.security import CheckAccess
from typing import List

router = APIRouter(prefix="/user", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    user_service: UserServiceDependency, current_user: CurrentUserDependency
):
    # FIX: Pass current_user.id (str) instead of the user object
    return await user_service.get_user_by_id(current_user.id)


@router.put("/me", response_model=UserResponse)  # FIX: Changed from GET to PUT
async def update_my_profile(
    data: UserUpdate,
    user_service: UserServiceDependency,
    current_user: CurrentUserDependency,
):
    # FIX: Pass current_user.id (str)
    return await user_service.update_user(current_user.id, data)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_profile(
    current_user: CurrentUserDependency,
    user_service: UserServiceDependency,
):
    # FIX: Added 'await'
    await user_service.soft_delete_user(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- ADMIN PANEL ---


@router.get("/", dependencies=[Depends(CheckAccess("users", "read"))])
async def get_all_users(
    user_service: UserServiceDependency,
    skip: int = 0,
    limit: int = 100,
):
    # Note: Ensure get_all_users is implemented in your UserService class
    return await user_service.get_all_users(skip, limit)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(CheckAccess("users", "read"))],
)
async def get_user_by_id_admin(
    user_service: UserServiceDependency,
    user_id: str,
):
    return await user_service.get_user_by_id(user_id)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(CheckAccess("users", "write"))],
)
async def update_user_admin(
    user_service: UserServiceDependency,
    user_id: str,
    user_data: UserUpdate,
):
    return await user_service.update_user(user_id, user_data)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(CheckAccess("users", "delete"))],
)
async def delete_user_admin(
    user_service: UserServiceDependency,
    user_id: str,
):
    await user_service.soft_delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
