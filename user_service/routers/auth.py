from passlib.context import CryptContext
from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from ..database import SessionLocal
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from starlette import status
from ..models import Users
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone


router = APIRouter(
    prefix='/auth',
    tags=['auth']
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SECRET_KEY = '987654321c234567890'
ALGORITHM = 'HS256'

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
db_dependency = Annotated[Session, Depends(get_db)]


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


def authenticate_user(username: str, password: str, db: db_dependency):
    user = db.query(Users).filter(Users.username == username).first()
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


@router.post('/create_user', status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    if db.query(Users).filter(Users.email == create_user_request.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(Users).filter(Users.username == create_user_request.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    create_user_model = Users(
        username=create_user_request.username,
        email=create_user_request.email,
        hashed_password=bcrypt_context.hash(create_user_request.password),
        contact_number=create_user_request.contact_number,
        role = create_user_request.role
    )
    db.add(create_user_model)
    db.commit()


@router.post('/token', response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate credentials')
    token = create_access_token(
        user.username, user.user_id, user.role, timedelta(minutes=20))
    return {
        'access_token': token,
        'token_type': 'bearer'}


@router.get('/get_current_user', status_code=status.HTTP_200_OK)
async def get_current_user(token: Annotated[str, Depends(Oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, ALGORITHM)
        username: str = payload.get('username')
        id: int = payload.get('id')
        role: str = payload.get('role')
        if username is None or id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate credentials')
        return {"username": username, "id": id, "role": role}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate credentials')



@router.post('/login_for_id', status_code=status.HTTP_200_OK)
async def login_for_user_id(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate credentials')
    user_id = user.user_id
    return {'user_id': user_id}