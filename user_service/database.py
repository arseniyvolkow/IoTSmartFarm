from sqlalchemy import create_engine
from sqlalchemy. orm import sessionmaker, declarative_base
import os

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER_DATABASE_USERNAME')}:"
    f"{os.getenv('POSTGRES_USER_DATABASE_PASSWORD')}@"
    f"{os.getenv('POSTGRES_USER_DATABASE_HOST')}:5432/"
    f"{os.getenv('POSTGRES_USER_DATABASE_NAME')}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
