from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File
from ..database import get_db
from sqlalchemy.orm import Session
from typing import Annotated, Optional
import httpx
from starlette import status
from ..models import Devices, Farms
from ..utils import get_current_user
from sqlalchemy import select
from ..services.device_service import DeviceService
from ..schemas import AddNewDevice, CursorPagination
from ..services.farm_service import FarmService

router = APIRouter(prefix="/devices", tags=["Devices"])


db_dependency = Annotated[Session, Depends(get_db)]


@router.post(
    "/device",
    status_code=status.HTTP_201_CREATED,
)
async def new_device(db: db_dependency, device_data: AddNewDevice):
    async with httpx.AsyncClient() as client:
        try:
            user_service_response = await client.post(
                "http://user_service:8005/auth/login_for_id",
                data={
                    "username": device_data.username,
                    "password": device_data.password,
                },
            )
            if user_service_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect login data",
                )

            user_info = user_service_response.json()
            user_id = user_info.get("user_id")

            device_service = DeviceService(db)
            device_entity = await device_service.create(user_id, device_data)
            return {"status": "success", "device_id": device_entity.unique_device_id}

        except httpx.RequestError:
            return {"status": "error", "message": "User service unavailable!"}


@router.get(
    "/unassigned-devices",
    status_code=status.HTTP_200_OK,
    response_model=CursorPagination,
)
async def get_unassigned_sensor(
    db: db_dependency,
    sort_column: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
):
    device_service = DeviceService(db)
    items, next_cursor = await device_service.get_unassigned_devices(
        current_user["id"], sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get("/all-devices", status_code=status.HTTP_200_OK)
async def all_devices(
    db: db_dependency,
    sort_column: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
):
    device_service = DeviceService(db)
    items, next_cursor = await device_service.get_all_devices(
        current_user["id"], sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get("/all-devices/{farm_id}", status_code=status.HTTP_200_OK)
async def farm_devices(
    db: db_dependency,
    sort_column: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    farm_id: str = Path(max_length=100),
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
):
    farm_service = FarmService(db)
    farm_entity = await farm_service.get(farm_id)
    await farm_service.check_access(farm_entity, current_user["id"])
    device_service = DeviceService(db)
    items, next_cursor = await device_service.get_farms_devices(
        current_user["id"], farm_entity, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.patch("/assign-device-to-farm", status_code=status.HTTP_200_OK)
async def assign_device(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    device_id: str = Query(max_length=100),
    farm_id: str = Query(max_length=100),
):
    farm_service = FarmService(db)
    farm_entity = await farm_service.get(farm_id)
    await farm_service.check_access(farm_entity, current_user["id"])
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user["id"])
    await device_service.assign_device_to_farm(device_entity, farm_entity)
    return {"details": "Device assigned to farm!"}


@router.patch("/device/{device_id}", status_code=status.HTTP_200_OK)
async def update_device_info(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    new_status: str = Query(max_length=15, regex="^(active|inactive|maintenance)$"),
    device_id: str = Path(max_length=250),
):
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user["id"])
    await device_service.update(device_entity, status=new_status)
    return new_status


@router.delete("/device/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    device_id: str = Path(max_length=250),
):
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user["id"])
    await device_service.delete(device_entity)


@router.post("/upload_firmware/{device_id}", status_code=status.HTTP_200_OK)
async def device_firmware_update(
    db: db_dependency,
    current_user: Annotated[dict, Depends(get_current_user)],
    file: UploadFile = File(...),
    device_id: str = Path(max_length=100),
):
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user["id"])
    try:
        firmware = await file.read()
        async with httpx.AsyncClient() as client:
            device_response = await client.post(
                url=f"http://{device_entity.device_ip_address}/update",
                files={"firmware": firmware},
            )
            if device_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Firmware update failed with status code {device_response.status_code}: {device_response.text}",
                )
        return {"status": "success", "device_response": device_response.text}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


 