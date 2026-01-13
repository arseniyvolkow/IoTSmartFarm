from fastapi import APIRouter, status, Depends
from user_service.schemas import UserRegister, UserLogin, TokenPair, RefreshRequest, UserResponse
from user_service.dependencies import (
    db_dependency,
    get_token_payload,
    UserServiceDependency,
    AuthServiceDependency,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

print(f"DEBUG: TokenPair is {TokenPair}")
@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_new_user(
    db: db_dependency, new_user_info: UserRegister, user_service: UserServiceDependency
):
    created_user = user_service.create_user(new_user_info)
    return created_user


@router.post("/token", response_model=TokenPair)
async def login(
    login_data: UserLogin,
    auth_service: AuthServiceDependency,
):
    return await auth_service.login_user(login_data)


@router.post("/logout")
async def logout(
    auth_service: AuthServiceDependency,
    # This only decodes the string, it doesn't touch the DB
    payload: dict = Depends(get_token_payload),
):
    await auth_service.logout_user(payload)
    return {"detail": "Successfully logged out"}


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(
    request: RefreshRequest,
    auth_service: AuthServiceDependency,
):

    return await auth_service.refresh_access_token(request.refresh_token)
