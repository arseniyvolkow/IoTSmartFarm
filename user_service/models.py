from user_service.database import Base
import uuid
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import ForeignKey, String, Boolean
from typing import Optional, List
from datetime import datetime
from sqlalchemy.schema import UniqueConstraint


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    """Модель для хранения информации о пользователе."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, index=True, default=generate_uuid
    )
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)

    first_name: Mapped[Optional[str]] = mapped_column(String)
    last_name: Mapped[Optional[str]] = mapped_column(String)
    middle_name: Mapped[Optional[str]] = mapped_column(String)

    # Статус активности для "мягкого" удаления
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # FIX: Изменено на Optional[str] и добавлено nullable=True
    # Это позволяет создавать пользователя без немедленного назначения роли
    role_id: Mapped[Optional[str]] = mapped_column(ForeignKey("roles.id"), nullable=True)

    # Связь ORM (много к одному)
    role: Mapped[Optional["Role"]] = relationship(back_populates="users")

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, index=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(
        String, unique=True, index=True
    )  # 'admin', 'manager'

    can_read_all: Mapped[bool] = mapped_column(Boolean, default=False)
    can_write_all: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    
    # Двусторонняя связь с пользователями
    users: Mapped[List["User"]] = relationship(back_populates="role")

    access_list: Mapped[List["RoleAccess"]] = relationship(
        back_populates="role", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self):
        return f"<Role(name='{self.name}', all_R={self.can_read_all}, all_W={self.can_write_all})>"


class RoleAccess(Base):
    __tablename__ = "role_access"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, index=True, default=generate_uuid
    )

    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))

    # Название ресурса, например: "farms", "sensors"
    resource: Mapped[str] = mapped_column(String, index=True)

    # Boolean флаги (CRUD)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False)

    role: Mapped["Role"] = relationship(back_populates="access_list")

    # Уникальность: у одной роли может быть только одна запись про конкретный ресурс
    __table_args__ = (UniqueConstraint("role_id", "resource", name="uq_role_resource"),)

    def __repr__(self):
        return f"<Access(res='{self.resource}', R={self.can_read}, W={self.can_write}, D={self.can_delete})>"