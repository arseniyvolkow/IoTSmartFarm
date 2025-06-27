from typing import Any, Optional
from pydantic import BaseModel
from datetime import date

# Device Models


class SensorInfo(BaseModel):
    sensor_type: str
    units_of_measure: str
    max_value: float
    min_value: float


class AddNewDevice(BaseModel):
    username: str
    password: str
    unique_device_id: str
    device_ip_address: str
    model_number: str
    firmware_version: str
    sensors_list: list[SensorInfo]


class UpdateDeviceInfo(BaseModel):
    status: str


class DeviceSchema(BaseModel):
    unique_device_id: str
    user_id: int
    farm_id: str
    device_ip_address: str
    model_number: str
    firmware_version: str
    status: str


class CursorPagination(BaseModel):
    items: list[DeviceSchema]
    next_cursor: Optional[str] = None


# farms models


class FarmModel(BaseModel):
    """
    Represents the data model for a farm, including its name, total area, location,
    and an optional crop. Used for validating and transferring farm-related data.
    """

    farm_name: str
    total_area: int
    location: str
    crop: Optional[str] = None


# Crops models


class CropManagmentModel(BaseModel):
    planting_date: date
    expected_harvest_date: date
    current_grow_stage: str
    crop_type_id: str


#Error

class ErrorResponse(BaseModel):
    message: str
    details: Optional[Any] = None