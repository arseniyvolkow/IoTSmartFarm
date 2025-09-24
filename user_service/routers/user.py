from typing import Annotated, Optional
from pydantic import BaseModel, Field
from starlette import status
from fastapi import APIRouter, Depends, HTTPException
from ..database import get_db
from ..utils import user_dependency, db_dependency, bcrypt_context
from ..models import Users
from sqlalchemy import select
from ..schemas import UserInfoResponse, ChangeNumber, ChangePassword

router = APIRouter(prefix="/user", tags=["user"])


def check_permissions(role: str):
    def dependency(user: user_dependency):
        if user.get("role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return user

    return dependency


@router.get("/info", response_model=UserInfoResponse, status_code=status.HTTP_200_OK)
async def user_info(db: db_dependency, user: user_dependency):
    query = select(Users).filter(Users.user_id == user.get("id"))
    result = await db.execute(query)
    user_entity = result.scalar_one_or_none()
    if user_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    return user_entity


@router.put("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    db: db_dependency, user: user_dependency, change_password: ChangePassword
):
    query = select(Users).filter(Users.user_id == user.get("id"))
    result = await db.execute(query)
    user_entity = result.scalar_one_or_none()
    if user_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if not bcrypt_context.verify(
        change_password.old_password, user_entity.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    user_entity.hashed_password = bcrypt_context.hash(change_password.new_password)
    await db.commit()


@router.put("/change-number", status_code=status.HTTP_204_NO_CONTENT)
async def change_number(
    db: db_dependency, user: user_dependency, change_number_request: ChangeNumber
):
    query = select(Users).filter(Users.user_id == user.get("id"))
    result = await db.execute(query)
    user_entity = result.scalar_one_or_none()
    if user_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    user_entity.contact_number = change_number_request.new_number
    await db.commit()
