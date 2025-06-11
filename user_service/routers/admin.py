from fastapi import APIRouter, Depends, HTTPException, Path
from starlette import status
from ..database import get_db
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession
from .auth import get_current_user
from ..models import Users
from pydantic import BaseModel
from sqlalchemy import select, delete


def check_admin_permissions(current_user: Annotated[dict, Depends(get_current_user)]):
    """
    Dependency to ensure current user has admin role.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(check_admin_permissions)]
)


db_dependency = Annotated[AsyncSession, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


class New_role(BaseModel):
    id_of_user: int
    role: str


class UserResponse(BaseModel):
    """Response model for user data"""

    user_id: int
    username: str
    email: str
    role: str
    contact_number: str = None

    class Config:
        from_attributes = True


@router.get(
    "/get_all_users", response_model=List[UserResponse], status_code=status.HTTP_200_OK
)
async def get_all_users(db: db_dependency, user: user_dependency):
    query = select(Users)
    result = await db.execute(query)
    users = result.scalars().all
    return users


@router.put("/change_users_role", status_code=status.HTTP_204_NO_CONTENT)
async def change_users_role(
    db: db_dependency, user: user_dependency, change_user: New_role
):
    query = select(Users).filter(Users.id == change_user.id_of_user)
    result = await db.execute(query)
    user_entity = result.scalar_one_or_none()
    if user_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {change_user.user_id} not found!",
        )
    if user_entity.user_id == user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role.",
        )
    user_entity.role = change_user.role
    await db.commit()
    await db.refresh(user_entity)


@router.get("/delete_user/{user_to_delete_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(db: db_dependency, user: user_dependency, user_to_delete_id: int):
    check_query = select(Users).filter(Users.user_id == user_to_delete_id)
    check_result = await db.execute(check_query)
    user_to_delete = check_result.scalar_one_or_none()
    if user_to_delete is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_to_delete_id} not found.",
        )

    if user_to_delete_id == user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    if user_to_delete.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete another admin account.",
        )

    delete_query = delete(Users).where(Users.user_id == user_to_delete_id)
    result = await db.execute(delete_query)
    await db.commit()

    if result.rowcount == 0:
        # This case should ideally be caught by the initial existence check,
        # but it's a good safeguard if concurrent operations are possible.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_to_delete_id} not found or already deleted.",
        )
    return {"details": "User deleted"}


@router.get(
    "/get_user/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK
)
async def get_user_by_id(
    db: db_dependency,
    user: user_dependency,
    user_id: int = Path(gt=0, description="ID of user to retrieve"),
):
    query = select(Users).filter(Users.user_id == user_id)
    result = await db.execute(query)
    user_entity = result.scalar_one_or_none()

    if user_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    return user_entity


@router.get(
    "/users_by_role/{role}",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
)
async def get_users_by_role(
    db: db_dependency,
    user: user_dependency,
    role: str = Path(min_length=1, description="Role to filter by"),
):
    query = select(Users).filter(Users.role == role)
    result = await db.execute(query)
    users = result.scalars().all()

    return users
