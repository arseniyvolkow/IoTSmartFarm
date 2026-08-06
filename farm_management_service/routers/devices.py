import json
import os

import aiomqtt
from fastapi import APIRouter, File, HTTPException, Path, Query, Request, UploadFile
from starlette import status

from farm_management_service.dependencies import (
    ActuatorServiceDependency,
    CurrentUserDependency,
    DeviceServiceDependency,
    FarmServiceDependency,
    SensorServiceDependency,
    db_dependency,
)
from farm_management_service.schemas import DeviceCreate, DevicePagination, DeviceRead

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("/device", status_code=status.HTTP_201_CREATED, response_model=DeviceRead)
async def new_device(
    device_service: DeviceServiceDependency, device_data: DeviceCreate
) -> DeviceRead:
    try:
        result = await device_service.create(device_data)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e!s}",
        )


@router.get(
    "/list-of-new-devices",
    status_code=status.HTTP_200_OK,
    response_model=DevicePagination,
)
async def get_list_of_new_devices(
    device_service: DeviceServiceDependency,
    sort_column: str | None = None,
    cursor: str | None = Query(None),
    limit: int | None = Query(10, ge=10, le=200),
) -> DevicePagination:
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
    current_user: CurrentUserDependency,
    device_service: DeviceServiceDependency,
    sort_column: str | None = None,
    cursor: str | None = Query(None),
    limit: int | None = Query(10, ge=10, le=200),
) -> DevicePagination:
    items, next_cursor = await device_service.get_unassigned_to_farm_devices(
        current_user.id, sort_column, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get(
    "/all-devices", status_code=status.HTTP_200_OK, response_model=DevicePagination
)
async def list_devices(
    current_user: CurrentUserDependency,
    device_service: DeviceServiceDependency,
    farm_service: FarmServiceDependency,
    farm_id: str | None = Query(None, max_length=100),
    sort_column: str | None = None,
    cursor: str | None = Query(None),
    limit: int | None = Query(10, ge=10, le=200),
) -> DevicePagination:
    if farm_id:
        farm_entity = await farm_service.get(farm_id)
        await farm_service.check_access(farm_entity, current_user)
    items, next_cursor = await device_service.get_user_devices(
        current_user.id, sort_column, farm_id, cursor, limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.patch(
    "/assign-farm-to-device", status_code=status.HTTP_200_OK, response_model=DeviceRead
)
async def assign_device(
    current_user: CurrentUserDependency,
    device_service: DeviceServiceDependency,
    farm_service: FarmServiceDependency,
    device_id: str = Query(max_length=100),
    farm_id: str = Query(max_length=100),
) -> DeviceRead:
    farm_entity = await farm_service.get(farm_id)
    await farm_service.check_access(farm_entity, current_user)
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user)
    updated_device_entity = await device_service.update(
        device_entity, farm_id=farm_entity.farm_id
    )
    return updated_device_entity


@router.patch("/assign-user-to-device", status_code=status.HTTP_200_OK)
async def assign_user_to_device(
    db: db_dependency,
    current_user: CurrentUserDependency,
    device_service: DeviceServiceDependency,
    sensor_service: SensorServiceDependency,
    actuator_service: ActuatorServiceDependency,
    device_id: str = Query(max_length=100),
):
    device_entity = await device_service.get(device_id)

    if device_entity.user_id == None:
        # Update the device with user_id
        await device_service.update(device_entity, user_id=current_user.id)

        # Update all sensors associated with this device (if sensors have user_id field)
        await sensor_service.assign_user_to_device_sensors(
            device_id, current_user.id
        )

        # Update all actuators associated with this device (if actuators have user_id field)
        await actuator_service.assign_user_to_device_actuators(
            device_id, current_user.id
        )

    return {"details": "Device assigned to user!"}


@router.patch("/device/{device_id}", status_code=status.HTTP_200_OK)
async def update_device_info(
    current_user: CurrentUserDependency,
    device_service: DeviceServiceDependency,
    new_status: str = Query(max_length=15, pattern="^(active|inactive|maintenance)$"),
    device_id: str = Path(max_length=250),
):
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user)
    await device_service.update(device_entity, status=new_status.upper())
    return new_status


@router.delete("/device/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    current_user: CurrentUserDependency,
    device_service: DeviceServiceDependency,
    device_id: str = Path(max_length=250),
):
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user)
    await device_service.delete(device_entity)


@router.post("/upload_firmware/{device_id}", status_code=status.HTTP_200_OK)
async def device_firmware_update(
    request: Request,
    current_user: CurrentUserDependency,
    device_service: DeviceServiceDependency,
    file: UploadFile = File(...),
    device_id: str = Path(max_length=100),
):
    device_entity = await device_service.get(device_id)
    await device_service.check_access(device_entity, current_user)
    try:
        # 1. Save firmware locally in the mounted static directory
        firmware_dir = "/home/arseniy/Projects/IoTSmartFarm/firmware"
        os.makedirs(firmware_dir, exist_ok=True)
        file_path = os.path.join(firmware_dir, file.filename)
        
        firmware_content = await file.read()
        with open(file_path, "wb") as f:
            f.write(firmware_content)
            
        # 2. Construct the download URL
        # For production, backend IP/domain would be used. Using host header for now.
        base_url = str(request.base_url).rstrip('/')
        download_url = f"{base_url}/api/farm-management-service/firmware/{file.filename}"
        
        # 3. Publish MQTT Command
        broker = os.getenv("MQTT_BROKER_URL", "mosquitto")
        port = int(os.getenv("MQTT_BROKER_PORT", 1883))
        username = os.getenv("MQTT_USERNAME")
        password = os.getenv("MQTT_PASSWORD")
        
        async with aiomqtt.Client(hostname=broker, port=port, username=username, password=password) as client:
            payload = json.dumps({"command": "update_firmware", "url": download_url})
            await client.publish(f"device/{device_id}/commands", payload)
            
        return {"status": "success", "message": "OTA command published via MQTT", "url": download_url}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/provision", status_code=status.HTTP_201_CREATED)
async def provision_device(
    mac_address: str = Query(..., description="The unique MAC address of the device"),
    setup_token: str = Query(..., description="Factory burned setup token"),
    device_service: DeviceServiceDependency = None
):
    # In a real scenario, setup_token is verified against a secure database or .env
    expected_token = os.getenv("DEVICE_SETUP_TOKEN", "default_secure_token")
    if setup_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid setup token")
        
    # Auto-create device if it doesn't exist (Zero-Touch Provisioning)
    # Using a dummy model_number/firmware_version for ZTP
    device_data = DeviceCreate(
        unique_device_id=mac_address,
        device_ip_address="0.0.0.0", # IP no longer strictly needed for connection
        model_number="ZTP-ESP32",
        firmware_version="1.0.0"
    )
    
    device = await device_service.create(device_data)
    
    # Return device ID and credentials so the device can store them and connect to MQTT
    return {
        "status": "provisioned",
        "device_id": device.device_id,
        "mqtt_broker": os.getenv("MQTT_BROKER_URL", "mosquitto"),
        "mqtt_port": int(os.getenv("MQTT_BROKER_PORT", 1883)),
        "mqtt_username": os.getenv("MQTT_USERNAME"),
        "mqtt_password": os.getenv("MQTT_PASSWORD"),
        "commands_topic": f"device/{device.device_id}/commands",
        "data_topic": f"device/{device.device_id}/data"
    }
