from fastapi import HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from farm_management_service.models import FarmAccess, Farms
from farm_management_service.schemas import FarmAccessCreate
from farm_management_service.enums import AccessLevel

class AccessService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def grant_access(self, farm_id: str, access_data: FarmAccessCreate, grantor_id: str):
        # 1. Verify grantor is the OWNER of the farm
        farm_query = select(Farms).filter(Farms.farm_id == farm_id)
        result = await self.db.execute(farm_query)
        farm = result.scalar_one_or_none()

        if not farm:
            raise HTTPException(status_code=404, detail="Farm not found")

        if farm.user_id != grantor_id:
            raise HTTPException(
                status_code=403, 
                detail="Only the farm owner can grant access"
            )

        # 2. Check if access already exists
        existing_access_query = select(FarmAccess).filter(
            FarmAccess.farm_id == farm_id,
            FarmAccess.user_id == access_data.user_id
        )
        existing_result = await self.db.execute(existing_access_query)
        existing_access = existing_result.scalar_one_or_none()

        if existing_access:
            # Update existing access
            existing_access.access_level = access_data.access_level
            await self.db.commit()
            await self.db.refresh(existing_access)
            return existing_access

        # 3. Create new access entry
        new_access = FarmAccess(
            farm_id=farm_id,
            user_id=access_data.user_id,
            access_level=access_data.access_level
        )
        self.db.add(new_access)
        await self.db.commit()
        await self.db.refresh(new_access)
        return new_access

    async def revoke_access(self, farm_id: str, target_user_id: str, requestor_id: str):
        # 1. Verify requestor is OWNER
        farm_query = select(Farms).filter(Farms.farm_id == farm_id)
        result = await self.db.execute(farm_query)
        farm = result.scalar_one_or_none()

        if not farm:
            raise HTTPException(status_code=404, detail="Farm not found")

        if farm.user_id != requestor_id:
            raise HTTPException(
                status_code=403, 
                detail="Only the farm owner can revoke access"
            )

        # 2. Delete access entry
        query = delete(FarmAccess).filter(
            FarmAccess.farm_id == farm_id,
            FarmAccess.user_id == target_user_id
        )
        result = await self.db.execute(query)
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Access entry not found")
            
        await self.db.commit()

    async def list_access(self, farm_id: str, requestor_id: str):
        # 1. Verify requestor is OWNER (or maybe allow ADMIN/READ access users to see who else is there?)
        # For now, let's stick to Owner only or explicit ADMIN access.
        
        # Check permissions (Owner OR Admin Access)
        has_perm = await self.has_access(farm_id, requestor_id, AccessLevel.ADMIN)
        if not has_perm:
             raise HTTPException(
                status_code=403, 
                detail="Not enough permissions to view access list"
            )

        query = select(FarmAccess).filter(FarmAccess.farm_id == farm_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def has_access(self, farm_id: str, user_id: str, required_level: AccessLevel) -> bool:
        # 1. Check if Owner
        farm_query = select(Farms).filter(Farms.farm_id == farm_id)
        result = await self.db.execute(farm_query)
        farm = result.scalar_one_or_none()
        
        if not farm:
            return False # Or raise 404? Logic depends on usage context.
            
        if farm.user_id == user_id:
            return True # Owner has all permissions

        # 2. Check Access Table
        access_query = select(FarmAccess).filter(
            FarmAccess.farm_id == farm_id,
            FarmAccess.user_id == user_id
        )
        access_result = await self.db.execute(access_query)
        access_entry = access_result.scalar_one_or_none()

        if not access_entry:
            return False

        # 3. Compare Levels
        # Logic: ADMIN > WRITE > READ
        user_level = access_entry.access_level
        
        if required_level == AccessLevel.READ:
            return True # Any level can read
        
        if required_level == AccessLevel.WRITE:
            return user_level in [AccessLevel.WRITE, AccessLevel.ADMIN]
            
        if required_level == AccessLevel.ADMIN:
            return user_level == AccessLevel.ADMIN
            
        return False
