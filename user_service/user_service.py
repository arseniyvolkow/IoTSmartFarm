from sqlalchemy import update, select
import re
from fastapi import HTTPException, status
from .models import User, Role
from .schemas import UserRegister, UserUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from .security import hash_password
from typing import Optional


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: str) -> User:
        """Получить пользователя по ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Получить пользователя по Email (для вну  тренних проверок)."""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete_user(self, user_id: str):
        query = update(User).where(User.id == user_id).values(is_active=False)
        await self.db.execute(query)
        await self.db.commit()

    async def create_user(self, new_user: UserRegister):
        email_exists = await self.db.execute(
            select(User).filter(User.email == new_user.email)
        )
        if email_exists.scalars().first():
            raise HTTPException(status_code=400, detail="Email already registered")
        # check if username exist
        username_exists = await self.db.execute(
            select(User).filter(User.username == new_user.username)
        )
        if username_exists.scalars().first():
            raise HTTPException(status_code=400, detail="Username already exists")
        # password validation
        password = new_user.password
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
        create_user_model = User(
            email=new_user.email,
            hashed_password=hash_password(new_user.password),
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            middle_name=new_user.middle_name,
        )
        self.db.add(create_user_model)
        await self.db.commit()
        await self.db.refresh(create_user_model)
        return create_user_model

    async def update_user(self, user_id: str, user_update: UserUpdate) -> User:
        """Обновление профиля."""
        user = await self.get_user_by_id(user_id)

        if user_update.email is not None:
            # Проверка на дубликат email, если он меняется
            if user_update.email != user.email:
                if await self.get_user_by_email(user_update.email):
                    raise HTTPException(400, "Email already in use")
            user.email = user_update.email

        if user_update.password is not None:
            user.hashed_password = hash_password(user_update.password)

        if user_update.is_active is not None:
            # user.is_active = user_update.is_active # Если есть поле
            pass

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def assign_role_to_user(self, user_id: str, role_name: str) -> User:
        """
        Назначение роли пользователю.
        Пример: assign_role_to_user("123", "manager")
        """
        # 1. Ищем пользователя
        user = await self.get_user_by_id(user_id)

        # 2. Ищем роль
        stmt_role = select(Role).where(Role.name == role_name)
        role = (await self.db.execute(stmt_role)).scalars().first()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_name}' not found",
            )

        # 3. Обновляем связь
        user.role_id = role.id
        # Если бы использовали user.role = role, SQLAlchemy тоже бы поняла

        await self.db.commit()
        await self.db.refresh(user)  # Обновит объект, подтянув данные роли
        return user
