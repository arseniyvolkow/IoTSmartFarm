from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
import os
import logging

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('POSTGRES_USER_DATABASE_USERNAME')}:"
    f"{os.getenv('POSTGRES_USER_DATABASE_PASSWORD')}@"
    f"{os.getenv('POSTGRES_USER_DATABASE_HOST')}:5432/"
    f"{os.getenv('POSTGRES_USER_DATABASE_NAME')}"
)

# Debug logging (remove password for security)
debug_url = SQLALCHEMY_DATABASE_URL.replace(os.getenv('POSTGRES_USER_DATABASE_PASSWORD'), '***')
logger.info(f"Database URL: {debug_url}")

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)  # Add echo for SQL debugging
AsyncSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

class Base(DeclarativeBase):
    pass

async def get_db():
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()