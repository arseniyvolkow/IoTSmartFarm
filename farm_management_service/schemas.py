from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from farm_management_service.enums import AccessLevel, ActuatorState, DeviceStatus

T = TypeVar("T")

# Farm Access Models
class FarmAccessBase(BaseModel):
    user_id: str
    access_level: AccessLevel = AccessLevel.READ

class FarmAccessCreate(FarmAccessBase):
    pass

class FarmAccessRead(FarmAccessBase):
    access_id: str
    farm_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SensorBase(BaseModel):
    """Base model for shared sensor fields."""

    sensor_type: str
    units_of_measure: str
    max_value: float
    min_value: float


class SensorCreate(SensorBase):
    device_id: str


class SensorRead(SensorBase):
    sensor_id: str
    device_id: str
    user_id: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SensorUpdate(BaseModel):
    sensor_type: str | None = None
    units_of_measure: str | None = None
    max_value: float | None = None
    min_value: float | None = None


# Actuators Models

class ActuatorBase(BaseModel):
    actuator_type: str
    available_states: dict
    current_state: ActuatorState = ActuatorState.OFF
    
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )

class ActuatorRead(ActuatorBase):
    actuator_id: str
    device_id: str
    user_id: str | None = None
    created_at: datetime
    updated_at: datetime
    

class ActuatorUpdate(BaseModel):
    current_state: ActuatorState | None = None
    actuator_type: str | None = None
    available_states: dict | None = None
    user_id: str | None = None
    device_id: str | None = None


class ActuatorCreate(ActuatorBase):
    device_id: str


# Device Models

class DeviceBase(BaseModel):
    unique_device_id: str
    device_ip_address: str
    model_number: str
    firmware_version: str


class DeviceCreate(DeviceBase):
    sensors_list: list[SensorBase] | None = None
    actuators_list: list[ActuatorBase] | None = None


class DeviceRead(DeviceBase):
    device_id: str
    user_id: str | None = None
    farm_id: str | None = None
    created_at: datetime
    sensors: list[SensorRead]
    actuators: list[ActuatorRead]
    model_config = ConfigDict(from_attributes=True)


class DeviceUpdate(BaseModel):
    device_ip_address: str | None = None
    model_number: str | None = None
    firmware_version: str | None = None
    status: DeviceStatus | None = None

    # Allows assigning a device to a new user or farm later
    user_id: str | None = None
    farm_id: str | None = None


# Farms models
class FarmBase(BaseModel):
    """
    Represents the data model for a farm, including its name, total area, location,
    and an optional crop. Used for validating and transferring farm-related data.
    """

    farm_name: str
    total_area: int
    location: str


class FarmRead(FarmBase):
    farm_id: str
    


class FarmCreate(FarmBase):
    pass


class FarmUpdate(BaseModel):
    farm_name: str | None = None
    total_area: int | None = None
    location: str | None = None



# CropManagment models


class CropManagmentBase(BaseModel):
    planting_date: date
    expected_harvest_date: date
    current_grow_stage: str


class CropManagmentRead(CropManagmentBase):
    crop_id: str
    farm_id: str

class CropManagmentCreate(CropManagmentBase):
    crop_type_id: str
    farm_id:str


class CropManagmentUpdate(BaseModel):
    planting_date: date | None = None
    expected_harvest_date: date | None = None
    current_grow_stage: str | None = None


# Crop models


class CropBase(BaseModel):
    crop_name: str


class CropCreate(CropBase):
    pass


class CropRead(CropBase):
    crop_id: str
    model_config = ConfigDict(from_attributes=True) 


# Error


class ErrorResponse(BaseModel):
    message: str
    details: Any | None = None


class CursorPagination(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


DevicePagination = CursorPagination[DeviceRead]
SensorPagination = CursorPagination[SensorRead]
ActuatorPagination = CursorPagination[ActuatorRead]
FarmPagination = CursorPagination[FarmRead]
CropManagmentPagination = CursorPagination[CropManagmentRead]
CropTypesPagination = CursorPagination[CropRead]