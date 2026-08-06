import asyncio
import logging

from sqlalchemy import select

from user_service.database import async_session_maker
from user_service.models import Role, User
from user_service.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_admin():
    async with async_session_maker() as session:
        # Check if admin role exists
        stmt = select(Role).where(Role.name == "admin")
        result = await session.execute(stmt)
        admin_role = result.scalars().first()

        if not admin_role:
            admin_role = Role(name="admin", can_read_all=True, can_write_all=True)
            session.add(admin_role)
            await session.flush()
            logger.info("Admin role created.")

        # Check if admin user exists
        stmt = select(User).where(User.email == "admin_final@example.com")
        result = await session.execute(stmt)
        admin_user = result.scalars().first()

        if not admin_user:
            hashed_password = await hash_password("Admin@123!")  # Default password
            admin_user = User(
                email="admin_final@example.com",
                hashed_password=hashed_password,
                first_name="Admin",
                last_name="Final",
                middle_name="",
                role_id=admin_role.id,
            )
            session.add(admin_user)
            await session.commit()
            logger.info("Admin user created.")
        else:
            logger.info("Admin user already exists.")


if __name__ == "__main__":
    asyncio.run(seed_admin())
