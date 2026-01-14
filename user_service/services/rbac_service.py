from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from user_service.models import Role, RoleAccess

class RBACService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_role(
        self, 
        name: str, 
        can_read_all: bool = False, 
        can_write_all: bool = False
    ) -> Role:
        stmt = select(Role).where(Role.name == name)
        result = await self.db.execute(stmt)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail=f"Role '{name}' already exists")

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
        stmt = select(Role).where(Role.name == name).options(selectinload(Role.access_list))
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
        # 1. Get role ID
        role = await self.get_role_by_name(role_name)

        # 2. Perform UPSERT
        insert_stmt = insert(RoleAccess).values(
            role_id=role.id,
            resource=resource,
            can_read=can_read,
            can_write=can_write,
            can_delete=can_delete
        )

        do_update_stmt = insert_stmt.on_conflict_do_update(
            constraint='uq_role_resource',
            set_={
                "can_read": insert_stmt.excluded.can_read,
                "can_write": insert_stmt.excluded.can_write,
                "can_delete": insert_stmt.excluded.can_delete
            }
        )

        await self.db.execute(do_update_stmt)
        await self.db.commit()

        # FIX: Explicitly refresh the role to force reload the access_list relationship
        # This ensures the UPSERTED rows are visible in the returned object
        await self.db.refresh(role, ["access_list"])
        return role

    async def get_all_roles(self) -> List[Role]:
        stmt = select(Role).options(selectinload(Role.access_list))
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_role(self, role_name: str):
        role = await self.get_role_by_name(role_name)
        await self.db.delete(role)
        await self.db.commit()