from passlib.context import CryptContext
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from ..database import get_db
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


load_dotenv()

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)


SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set")

ALGORITHM = 'HS256'

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
db_dependency = Annotated[AsyncSession, Depends(get_db)]


Oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')


class Token(BaseModel):
    access_token: str
    token_type: str


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    contact_number: str
    role: str


class UserResponse(BaseModel):
    username: str
    id: int
    role: str


async def authenticate_user(username: str, password: str, db: db_dependency):
    query = select(Users).filter(Users.username == username)
    result = await db.execute(query)
    user = result.scalars().first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.hashed_password):
        return False
    return user


def create_access_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    encode = {"username": username, "id": user_id, "role": role}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(Oauth2_bearer)]):
    """
    Dependency function to extract user info from JWT token.
    Use this with Depends() in other routes.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, ALGORITHM)
        username: str = payload.get('username')
        user_id: int = payload.get('id')
        role: str = payload.get('role')
        
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Could not validate credentials',
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return {"username": username, "id": user_id, "role": role}
    
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Could not validate credentials',
            headers={"WWW-Authenticate": "Bearer"}
        )


@router.post('/create_user', status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    #check if email exist
    email_exists = await db.execute(select(Users).filter(Users.email == create_user_request.email))
    if email_exists.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    #check if username exist
    username_exists = await db.execute(select(Users).filter(Users.username == create_user_request.username))
    if username_exists.scalars().first():
        raise HTTPException(status_code=400, detail="Username already exists")
    #password validation
    password = create_user_request.password
    if (len(password) < 8 or
        not re.search(r"[A-Z]", password) or
        not re.search(r"[a-z]", password) or
        not re.search(r"\d", password) or
            not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long and include uppercase, lowercase, digit, and special character."
        )
    
    create_user_model = Users(
        username=create_user_request.username,
        email=create_user_request.email,
        hashed_password=bcrypt_context.hash(password),
        contact_number=create_user_request.contact_number,
        role=create_user_request.role
    )
    db.add(create_user_model)
    await db.commit()
    await db.refresh(create_user_model)

    return {"detail": "User created successfully", "user_id": create_user_model.user_id}



@router.post('/token', response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
    db: db_dependency
):
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Could not validate credentials'
            )
    token = create_access_token(
        user.username, 
        user.user_id, 
        user.role, 
        timedelta(minutes=20)
    )
    return {
        'access_token': token,
        'token_type': 'bearer'
    }


@router.get('/get_current_user', response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_current_user(current_user: Annotated[dict, Depends(get_current_user)]):
    return {
        "username": current_user["username"],
        "id": current_user["id"], 
        "role": current_user["role"]
    }


@router.post('/login_for_id', status_code=status.HTTP_200_OK)
async def login_for_user_id(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
    db: db_dependency
):
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Could not validate credentials'
        )
    return {'user_id': user.user_id}
