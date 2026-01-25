from fastapi import APIRouter, Depends, status, Path
from typing import List, Annotated
from farm_management_service.services.access_service import AccessService
from farm_management_service.dependencies import get_access_service, CurrentUserDependency
from farm_management_service.schemas import FarmAccessCreate, FarmAccessRead

router = APIRouter(prefix="/farms", tags=["Access Control"])

AccessServiceDependency = Annotated[AccessService, Depends(get_access_service)]

@router.post("/{farm_id}/access", status_code=status.HTTP_201_CREATED, response_model=FarmAccessRead)
async def grant_access(
    farm_id: str,
    access_data: FarmAccessCreate,
    access_service: AccessServiceDependency,
    current_user: CurrentUserDependency
):
    return await access_service.grant_access(farm_id, access_data, current_user.id)

@router.delete("/{farm_id}/access/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_access(
    farm_id: str,
    user_id: str,
    access_service: AccessServiceDependency,
    current_user: CurrentUserDependency
):
    await access_service.revoke_access(farm_id, user_id, current_user.id)

@router.get("/{farm_id}/access", response_model=List[FarmAccessRead])
async def list_access(
    farm_id: str,
    access_service: AccessServiceDependency,
    current_user: CurrentUserDependency
):
    return await access_service.list_access(farm_id, current_user.id)
