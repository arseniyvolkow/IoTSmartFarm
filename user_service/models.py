from .database import Base
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import Column, Integer, String


class Users(Base):
    __tablename__ = 'users'

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    contact_number: Mapped[str] = mapped_column(String)
