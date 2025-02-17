from fastapi import HTTPException
from starlette import status
import httpx
import abc
from sqlalchemy.orm import Session


async def login_via_token(token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url_of_user_service = 'http://user_service:8005/auth/get_current_user'
    async with httpx.AsyncClient() as client:
        try:
            user_service_response = await client.get(url=url_of_user_service, headers=headers)
            if user_service_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail='Incorrect login data')
            return user_service_response.json()
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='User service unavailable!')


class BaseService(abc.ABC):
    def __init__(self, db:Session):
        self.db = db 
    
    def get():
        pass

    def create():
        pass 

    def check_access(entity, user_id):
        if entity.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail='Access denied!'
            )

    def update(self, entity, **kwargs):
        for key, value in kwargs.items():
            setattr(entity, key, value)
        self.db.commit()


    def delete(self, entity):
        self.db.delete(entity)
        self.db.commit()