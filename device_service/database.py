from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Debug prints
print("Database Username:", os.getenv('POSTGRES_DEVICE_DATABASE_USERNAME'))
print("Database Host:", os.getenv('POSTGRES_DEVICE_DATABASE_HOST'))
print("Database Name:", os.getenv('POSTGRES_DEVICE_DATABASE_NAME'))
print("Full Connection String:", f"postgresql+psycopg2://{os.getenv('POSTGRES_DEVICE_DATABASE_USERNAME')}:"
      f"[PASSWORD]@"  # Don't print actual password
      f"{os.getenv('POSTGRES_DEVICE_DATABASE_HOST')}:5432/"
      f"{os.getenv('POSTGRES_DEVICE_DATABASE_NAME')}")

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_DEVICE_DATABASE_USERNAME')}:"
    f"{os.getenv('POSTGRES_DEVICE_DATABASE_PASSWORD')}@"
    f"{os.getenv('POSTGRES_DEVICE_DATABASE_HOST')}:5432/"
    f"{os.getenv('POSTGRES_DEVICE_DATABASE_NAME')}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()