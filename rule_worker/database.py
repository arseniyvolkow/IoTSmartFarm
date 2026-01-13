from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
import os
from contextlib import asynccontextmanager


SQLALCHEMY_DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('POSTGRES_RULE_DATABASE_USERNAME')}:"
    f"{os.getenv('POSTGRES_RULE_DATABASE_PASSWORD')}@"
    f"{os.getenv('POSTGRES_RULE_DATABASE_HOST')}:5432/"
    f"{os.getenv('POSTGRES_RULE_DATABASE_NAME')}"
)


engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
