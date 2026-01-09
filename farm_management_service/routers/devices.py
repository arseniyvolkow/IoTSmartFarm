from fastapi import APIRouter, HTTPException, Query, Path, UploadFile, File
from typing import Optional
import httpx
from starlette import status
from ..services.device_service import DeviceService
from ..schemas import DeviceCreate, DevicePagination, DeviceRead
from ..services.farm_service import FarmService
from ..services.actuators_service import ActuatorService
from ..services.sensor_service import SensorService
from ..utils import db_dependency, user_dependency


router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("/device", status_code=status.HTTP_201_CREATED, response_model=DeviceRead)
async def new_device(db: db_dependency, device_data: DeviceCreate) -> DeviceRead:
    try:
        device_service = DeviceService(db)
        result = await device_service.create(device_data)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.get(
    "/list-of-new-devices",
    status_code=status.HTTP_200_OK,
    response_model=DevicePagination,
)
async def get_list_of_new_devices(
    db: db_dependency,
    current_user: user_dependency,
    sort_column: Optional[str] = None,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
) -> DevicePagination:
    device_service = DeviceService(db)
    items, next_cursor = await device_service.get_unassigned_to_user_devices(
        sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get(
    "/unassigned-to-farm-devices",
    status_code=status.HTTP_200_OK,
    response_model=DevicePagination,
)
async def get_unassigned_sensor(
    db: db_dependency,
    current_user: user_dependency,
    sort_column: Optional[str] = None,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
) -> DevicePagination:
    device_service = DeviceService(db)
    items, next_cursor = await device_service.get_unassigned_to_farm_devices(
        current_user["id"], sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get(
    "/all-devices", status_code=status.HTTP_200_OK, response_model=DevicePagination
)
async def list_devices(
    db: db_dependency,
    current_user: user_dependency,
    farm_id: Optional[str] = Query(None, max_length=100),
    sort_column: Optional[str] = None,
    cursor: Optional[str] = Query(None),
    limit: Optional[int] = Query(10, ge=10, le=200),
) -> DevicePagination:
    device_service = DeviceService(db)
    user_id = current_user["id"]

    if farm_id:
        farm_service = FarmService(db)
        farm_entity = await farm_service.get(farm_id)
        await farm_service.check_access(farm_entity, user_id)
    items, next_cursor = await device_service.get_user_devices(
        user_id, farm_entity, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.patch(
    "/assign-farm-to-device", status_code=status.HTTP_200_OK, response_model=DeviceRead
)
async def assign_device(
    db: db_dependency,
    current_user: user_dependency,
    device_id: str = Query(max_length=100),
    farm_id: str = Query(max_length=100),
) -> DeviceRead:
    farm_service = FarmService(db)
    farm_entity = await farm_service.get(farm_id)
    await farm_service.check_access(farm_entity, current_user["id"])
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user["id"])
    updated_device_entity = await device_service.update(
        device_entity, farm_id=farm_entity.farm_id
    )
    return updated_device_entity


@router.patch("/assign-user-to-device", status_code=status.HTTP_200_OK)
async def assign_user_to_device(
    db: db_dependency,
    current_user: user_dependency,
    device_id: str = Query(max_length=100),
):
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)

    if device_entity.user_id == None:
        # Update the device with user_id
        await device_service.update(device_entity, user_id=current_user["id"])

        # Update all sensors associated with this device (if sensors have user_id field)
        sensor_service = SensorService(db)
        await sensor_service.assign_user_to_device_sensors(
            device_id, current_user["id"]
        )

        # Update all actuators associated with this device (if actuators have user_id field)
        actuator_service = ActuatorService(db)
        await actuator_service.assign_user_to_device_actuators(
            device_id, current_user["id"]
        )

    return {"details": "Device assigned to user!"}


@router.patch("/device/{device_id}", status_code=status.HTTP_200_OK)
async def update_device_info(
    db: db_dependency,
    current_user: user_dependency,
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
    current_user: user_dependency,
    device_id: str = Path(max_length=250),
):
    device_service = DeviceService(db)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user["id"])
    await device_service.delete(device_entity)


@router.post("/upload_firmware/{device_id}", status_code=status.HTTP_200_OK)
async def device_firmware_update(
    db: db_dependency,
    current_user: user_dependency,
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
