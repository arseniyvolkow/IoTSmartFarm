from fastapi import Depends, HTTPException, status
from user_service.database import db_dependency
from sqlalchemy import select
from user_service.models import User
from fastapi.security import HTTPBearer
from user_service.services.user_service import UserService
from typing import Annotated
from common.security import get_token_payload
from user_service.services.auth_service import AuthService
from user_service.services.rbac_service import RBACService

oauth2_scheme = HTTPBearer()


async def get_current_user(
    db: db_dependency, payload: dict = Depends(get_token_payload)
) -> User:
    # Use "sub" as per your login_user service logic
    user_id = payload.get("sub")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_user_service(db: db_dependency) -> UserService:
    return UserService(db)


async def get_auth_service(db: db_dependency) -> AuthService:
    return AuthService(db)


async def get_rbac_service(db: db_dependency) -> RBACService:
    return RBACService(db)


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
CurrentUserDependency = Annotated[User, Depends(get_current_user)]
RBACServiceDependency = Annotated[RBACService, Depends(get_rbac_service)]
