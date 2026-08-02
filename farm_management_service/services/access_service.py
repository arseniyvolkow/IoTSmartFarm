from fastapi import HTTPException
from farm_management_service.schemas import FarmAccessCreate
from farm_management_service.enums import AccessLevel
from farm_management_service.repositories.access_repository import AccessRepository

class AccessService:
    def __init__(self, access_repo: AccessRepository):
        self.access_repo = access_repo

    async def grant_access(self, farm_id: str, access_data: FarmAccessCreate, grantor_id: str):
        # 1. Verify grantor is the OWNER of the farm
        owner_id = await self.access_repo.get_farm_owner(farm_id)

        if not owner_id:
            raise HTTPException(status_code=404, detail="Farm not found")

        if owner_id != grantor_id:
            raise HTTPException(
                status_code=403, 
                detail="Only the farm owner can grant access"
            )

        # 2. Check if access already exists
        existing_access = await self.access_repo.get_access_entry(farm_id, access_data.user_id)

        if existing_access:
            # Update existing access
            return await self.access_repo.update_access(existing_access, access_data.access_level)

        # 3. Create new access entry
        return await self.access_repo.create_access(farm_id, access_data.user_id, access_data.access_level)

    async def revoke_access(self, farm_id: str, target_user_id: str, requestor_id: str):
        # 1. Verify requestor is OWNER
        owner_id = await self.access_repo.get_farm_owner(farm_id)

        if not owner_id:
            raise HTTPException(status_code=404, detail="Farm not found")

        if owner_id != requestor_id:
            raise HTTPException(
                status_code=403, 
                detail="Only the farm owner can revoke access"
            )

        # 2. Delete access entry
        rowcount = await self.access_repo.delete_access(farm_id, target_user_id)
        
        if rowcount == 0:
            raise HTTPException(status_code=404, detail="Access entry not found")

    async def list_access(self, farm_id: str, requestor_id: str):
        # 1. Verify requestor is OWNER (or maybe allow ADMIN/READ access users to see who else is there?)
        # Check permissions (Owner OR Admin Access)
        has_perm = await self.has_access(farm_id, requestor_id, AccessLevel.ADMIN)
        if not has_perm:
             raise HTTPException(
                status_code=403, 
                detail="Not enough permissions to view access list"
            )

        return await self.access_repo.get_all_access_for_farm(farm_id)

    async def has_access(self, farm_id: str, user_id: str, required_level: AccessLevel) -> bool:
        # 1. Check if Owner
        owner_id = await self.access_repo.get_farm_owner(farm_id)
        
        if not owner_id:
            return False
            
        if owner_id == user_id:
            return True # Owner has all permissions

        # 2. Check Access Table
        access_entry = await self.access_repo.get_access_entry(farm_id, user_id)

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
