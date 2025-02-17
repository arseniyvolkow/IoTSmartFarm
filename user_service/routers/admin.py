from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from ..database import SessionLocal
from typing import Annotated
from sqlalchemy.orm import Session
from .auth import get_current_user
from ..models import Users
from pydantic import BaseModel
from .user import check_premissions

router = APIRouter(
    prefix='/admin',
    tags=['admin'],
    dependencies=[Depends(check_premissions('admin'))]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependecy = Annotated[dict, Depends(get_current_user)]


class New_role(BaseModel):
    id_of_user: int
    role: str


@router.get('/get_all_users', status_code=status.HTTP_200_OK)
async def get_all_users(db: db_dependency, user: user_dependecy):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication needed!') 
    return db.query(Users).all()


@router.put('/change_users_role', status_code=status.HTTP_204_NO_CONTENT)
async def change_users_role(db: db_dependency, user: user_dependecy, change_user: New_role):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication needed!')
    user_entity = db.query(Users).filter(
        Users.id == change_user.id_of_user).first()
    if user_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='User not found!')
    user_entity.role = change_user.role
    db.add(user_entity)
    db.commit()


@router.get('/delete_user/{user_to_delete_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(db:db_dependency,user: user_dependecy, user_to_delete_id:int):
    user_to_delete_entity = db.query(Users).filter(Users.user_id == user_to_delete_id).delete()
    db.commit()