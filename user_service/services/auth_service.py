from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..schemas import TokenPair, UserLogin
from ..security import verify_password, create_access_token, create_refresh_token
from ..models import User
from ..security import decode_access_token
from common.redis_config import is_token_blacklisted


# Импортируем функцию для работы с Redis из common-библиотеки
# Если вы еще не настроили common/redis_client.py, этот импорт упадет.
# В таком случае закомментируйте его и логику логаута временно.
try:
    from common.redis_config import add_token_to_blacklist
except ImportError:
    # Заглушка, если библиотека common не найдена
    print("Warning: common.redis_client not found. Logout will not work.")

    async def add_token_to_blacklist(jti: str, expire_seconds: int):
        pass


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _create_payload(self, user: User) -> dict:
        role_name = "guest"
        global_perms = {"r_all": False, "w_all": False}
        resource_access = {}

        if user.role:
            role_name = user.role.name
            global_perms = {
                "r_all": getattr(user.role, "can_read_all", False),
                "w_all": getattr(user.role, "can_write_all", False),
            }
            for access in user.role.access_list:
                resource_access[access.resource] = {
                    "r": int(access.can_read),
                    "w": int(access.can_write),
                    "d": int(access.can_delete),
                }

        return {
            "sub": str(user.id),
            "email": user.email,
            "role": role_name,
            "g_perms": global_perms,
            "access": resource_access,
        }

    async def login_user(self, login_info: UserLogin) -> TokenPair:
        """Вход в систему: выдача пары токенов."""
        stmt = select(User).where(User.email == login_info.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not verify_password(
            login_info.password, user.hashed_password
        ):
            raise HTTPException(status_code=401, detail="Incorrect email or password")

        # Формируем Payload
        payload = self._create_payload(user)

        # Генерируем ПАРУ токенов
        # В Refresh токен кладем только sub (ID), чтобы он был легче,
        # так как права мы всё равно перечитаем из БД при обновлении.
        refresh_payload = {"sub": str(user.id)}

        return TokenPair(
            access_token=create_access_token(payload),
            refresh_token=create_refresh_token(refresh_payload),
        )

    async def logout_user(self, payload: dict):
        """
        Выход пользователя. Отзывает токен, помещая его JTI в черный список Redis.
        """
        jti = payload.get("jti")
        exp = payload.get("exp")

        if not jti or not exp:
            return

        # Вычисляем оставшееся время жизни токена
        now = datetime.now(timezone.utc).timestamp()
        ttl = int(exp - now)

        if ttl > 0:
            # Блокируем токен в Redis ровно на то время, пока он еще валиден
            await add_token_to_blacklist(jti, ttl)

    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Обновление токенов по Refresh Token."""

        # 1. Декодируем Refresh Token используя готовую функцию из security.py
        # Она сама проверит подпись и срок действия (exp) и выкинет HTTPException если что не так.
        payload = decode_access_token(refresh_token)

        jti = payload.get("jti")
        user_id = payload.get("sub")
        token_type = payload.get("type")
        exp = payload.get("exp")

        # 2. Проверки безопасности
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type. Expected 'refresh'.",
            )

        if await is_token_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )

        # 3. Token Rotation (Блокируем СТАРЫЙ refresh token)
        # Это защищает от кражи: если токен украли и использовали,
        # настоящий пользователь не сможет обновиться и поймет это (или наоборот).
        now = datetime.now(timezone.utc).timestamp()
        ttl = int(exp - now)
        if ttl > 0:
            await add_token_to_blacklist(jti, ttl)

        # 4. Получаем актуального пользователя из БД
        # Важно: Мы идем в БД, чтобы получить АКТУАЛЬНЫЕ права.
        # Если роль изменили 5 минут назад, новый Access Token будет уже с новой ролью.
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 5. Выдаем НОВУЮ пару
        new_payload = self._create_payload(user)
        new_refresh_payload = {"sub": str(user.id)}

        return TokenPair(
            access_token=create_access_token(new_payload),
            refresh_token=create_refresh_token(new_refresh_payload),
        )
