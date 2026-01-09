from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException

# Импортируем новые модели
from .models import Role, RoleAccess


class RBACService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_role(
        self, 
        name: str, 
        can_read_all: bool = False, 
        can_write_all: bool = False
    ) -> Role:
        """
        Создает новую роль.
        Поддерживает глобальные флаги can_read_all/can_write_all (для супер-админов).
        """
        # 1. Проверяем, существует ли роль
        stmt = select(Role).where(Role.name == name)
        result = await self.db.execute(stmt)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail=f"Role '{name}' already exists")

        # 2. Создаем
        new_role = Role(
            name=name, 
            can_read_all=can_read_all, 
            can_write_all=can_write_all
        )
        self.db.add(new_role)
        
        await self.db.commit()
        await self.db.refresh(new_role)
        return new_role

    async def get_role_by_name(self, name: str) -> Role:
        """Вспомогательный метод для получения роли по имени"""
        stmt = select(Role).where(Role.name == name)
        result = await self.db.execute(stmt)
        role = result.scalars().first()
        
        if not role:
            raise HTTPException(status_code=404, detail=f"Role '{name}' not found")
        return role

    async def set_role_access(
        self, 
        role_name: str, 
        resource: str, 
        can_read: bool = False, 
        can_write: bool = False, 
        can_delete: bool = False
    ) -> Role:
        """
        Устанавливает или обновляет права роли на конкретный ресурс.
        Использует PostgreSQL UPSERT (INSERT ... ON CONFLICT UPDATE).
        """
        # 1. Получаем роль (чтобы узнать её ID)
        role = await self.get_role_by_name(role_name)

        # 2. Подготавливаем запрос вставки (INSERT)
        insert_stmt = insert(RoleAccess).values(
            role_id=role.id,
            resource=resource,
            can_read=can_read,
            can_write=can_write,
            can_delete=can_delete
        )

        # 3. Добавляем логику "ON CONFLICT"
        # Если запись для (role_id, resource) уже есть (благодаря UniqueConstraint 'uq_role_resource'),
        # то мы обновляем булевы флаги.
        do_update_stmt = insert_stmt.on_conflict_do_update(
            constraint='uq_role_resource', # Должно совпадать с именем в __table_args__ модели
            set_={
                "can_read": insert_stmt.excluded.can_read,
                "can_write": insert_stmt.excluded.can_write,
                "can_delete": insert_stmt.excluded.can_delete
            }
        )

        await self.db.execute(do_update_stmt)
        await self.db.commit()
        
        # 4. Обновляем объект роли, чтобы поле role.access_list подтянуло свежие данные
        # (это работает благодаря lazy="selectin" в модели Role)
        await self.db.refresh(role) 
        
        return role


    async def get_all_roles(self) -> List[Role]:
        stmt = select(Role)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_role(self, role_name: str):
        role = await self.get_role_by_name(role_name)
        await self.db.delete(role)
        await self.db.commit()