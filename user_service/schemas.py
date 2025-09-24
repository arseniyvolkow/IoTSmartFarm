from pydantic import BaseModel, Field
from typing import Optional


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


class UserInfoResponse(BaseModel):
    user_id: int
    username: str
    email: str
    role: str
    contact_number: Optional[str] = None

    class Config:
        from_attributes = True


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


class ChangeNumber(BaseModel):
    new_number: str = Field(min_length=1, max_length=20)


class NewRole(BaseModel):
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