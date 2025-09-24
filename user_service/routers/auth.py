from passlib.context import CryptContext
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from starlette import status
from ..models import Users
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import os
from sqlalchemy import select
from dotenv import load_dotenv
import re
from ..schemas import Token, CreateUserRequest, UserResponse
from ..utils import (
    SECRET_KEY,
    db_dependency,
    bcrypt_context,
    user_dependency,
    ALGORITHM,
    authenticate_user,
    create_access_token,
)


load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/create_user", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    # check if email exist
    email_exists = await db.execute(
        select(Users).filter(Users.email == create_user_request.email)
    )
    if email_exists.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    # check if username exist
    username_exists = await db.execute(
        select(Users).filter(Users.username == create_user_request.username)
    )
    if username_exists.scalars().first():
        raise HTTPException(status_code=400, detail="Username already exists")
    # password validation
    password = create_user_request.password
    if (
        len(password) < 8
        or not re.search(r"[A-Z]", password)
        or not re.search(r"[a-z]", password)
        or not re.search(r"\d", password)
        or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)
    ):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long and include uppercase, lowercase, digit, and special character.",
        )

    create_user_model = Users(
        username=create_user_request.username,
        email=create_user_request.email,
        hashed_password=bcrypt_context.hash(password),
        contact_number=create_user_request.contact_number,
        role=create_user_request.role,
    )
    db.add(create_user_model)
    await db.commit()
    await db.refresh(create_user_model)

    return {"detail": "User created successfully", "user_id": create_user_model.user_id}


@router.post("/token", response_model=Token)
async def get_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency
):
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    token = create_access_token(
        user.username, user.user_id, user.role, timedelta(minutes=20)
    )
    return {"access_token": token, "token_type": "bearer"}


@router.get(
    "/get_current_user", status_code=status.HTTP_200_OK
)
async def get_user(current_user: user_dependency):
    return {
        "username": current_user["username"],
        "id": current_user["id"],
        "role": current_user["role"],
    }


# @router.post("/login_for_id", status_code=status.HTTP_200_SOK)
# async def login_for_user_id(
#     form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency
# ):
#     user = await authenticate_user(form_data.username, form_data.password, db)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Could not validate credentials",
#         )
#     return {"user_id": user.user_id}
