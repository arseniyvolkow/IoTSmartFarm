
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from user_service.models import User
from user_service.repositories.user_repository import RoleRepository, UserRepository
from user_service.schemas import UserRegister, UserUpdate
from user_service.security import hash_password


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.role_repo = RoleRepository(db)

    async def get_user_by_id(self, user_id: str) -> User:
        """Получить пользователя по ID."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """Получить пользователя по Email (для внутренних проверок)."""
        return await self.user_repo.get_by_email(email)

    async def soft_delete_user(self, user_id: str):
        user = await self.get_user_by_id(user_id)
        await self.user_repo.update(user, is_active=False)

    async def create_user(self, new_user: UserRegister):
        email_exists = await self.user_repo.get_by_email(new_user.email)
        if email_exists:
            raise HTTPException(status_code=400, detail="Email already registered")

        create_user_model = User(
            email=new_user.email,
            hashed_password=await hash_password(new_user.password),
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            middle_name=new_user.middle_name,
            role_id=None
        )
        return await self.user_repo.create(create_user_model)

    async def update_user(self, user_id: str, user_update: UserUpdate) -> User:
        """Обновление профиля пользователя."""
        user = await self.get_user_by_id(user_id)
    
        # Обновление Email с проверкой на уникальность
        if user_update.email is not None and user_update.email != user.email and await self.user_repo.get_by_email(user_update.email):
            raise HTTPException(400, "Email already in use")
    
        # Обновление пароля
        hashed_password = user.hashed_password
        if user_update.password is not None:
            hashed_password = await hash_password(user_update.password)
            
        kwargs = user_update.model_dump(exclude_unset=True)
        if "password" in kwargs:
            kwargs.pop("password")
            kwargs["hashed_password"] = hashed_password
            
        return await self.user_repo.update(user, **kwargs)

    async def assign_role_to_user(self, user_id: str, role_name: str) -> User:
        """
        Назначение роли пользователю.
        Пример: assign_role_to_user("123", "manager")
        """
        user = await self.get_user_by_id(user_id)
        role = await self.role_repo.get_by_name(role_name)

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_name}' not found",
            )

        return await self.user_repo.update(user, role_id=role.id)
