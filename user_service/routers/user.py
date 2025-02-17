from typing import Annotated
from pydantic import BaseModel, Field
from starlette import status
from fastapi import APIRouter, Depends, HTTPException
from ..database import SessionLocal
from sqlalchemy.orm import Session
from .auth import get_current_user
from ..models import Users
from passlib.context import CryptContext

router = APIRouter(
    prefix='/user',
    tags=['user']
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


def check_premissions(role: str):
    def dependency(user: user_dependency):
        if user.get('role') != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource"
            )
        return user
    return dependency


@router.get("/info", status_code=status.HTTP_200_OK)
async def user_info(db: db_dependency, user: user_dependency):
    print(user)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication needed!')
    user_entity = db.query(Users).filter(Users.user_id == user.get('id')).first()
    print(user_entity)
    return user_entity


@router.put('/change_password', status_code=status.HTTP_204_NO_CONTENT)
async def change_password(db: db_dependency, user: user_dependency, change_password: ChangePassword):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication needed!")
    user_entity = db.query(Users).filter(Users.id == user.get('id')).first()
    if not bcrypt_context.verify(change_password.old_password, user_entity.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Error on password change!")
    user_entity.hashed_password = bcrypt_context.hash(
        change_password.new_password)
    db.add(user_entity)
    db.commit()


@router.put('/change_number', status_code=status.HTTP_204_NO_CONTENT)
async def change_number(db: db_dependency, user: user_dependency, new_number: str):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed!")
    user_entity = db.query(Users).filter(Users.id == user.get("id"))
    user_entity.contact_number = new_number
    db.add(user_entity)
    db.commit()
