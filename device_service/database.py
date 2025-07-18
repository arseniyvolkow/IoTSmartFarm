from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
import os

# Debug prints
# print("Database Username:", os.getenv('POSTGRES_DEVICE_DATABASE_USERNAME'))
# print("Database Host:", os.getenv('POSTGRES_DEVICE_DATABASE_HOST'))
# print("Database Name:", os.getenv('POSTGRES_DEVICE_DATABASE_NAME'))
# print("Full Connection String:", f"postgresql+psycopg2://{os.getenv('POSTGRES_DEVICE_DATABASE_USERNAME')}:"
#       f"[PASSWORD]@"  # Don't print actual password
#       f"{os.getenv('POSTGRES_DEVICE_DATABASE_HOST')}:5432/"
#       f"{os.getenv('POSTGRES_DEVICE_DATABASE_NAME')}")

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('POSTGRES_DEVICE_DATABASE_USERNAME')}:"
    f"{os.getenv('POSTGRES_DEVICE_DATABASE_PASSWORD')}@"
    f"{os.getenv('POSTGRES_DEVICE_DATABASE_HOST')}:5432/"
    f"{os.getenv('POSTGRES_DEVICE_DATABASE_NAME')}"
)




engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine,class_=AsyncSession,)


class Base(DeclarativeBase):
    pass

async def get_db():
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()