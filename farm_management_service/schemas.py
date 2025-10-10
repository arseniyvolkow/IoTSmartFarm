from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import date, datetime
from typing import Optional, List, TypeVar, Generic
from enum import Enum as PyEnum
from .enums import ActuatorState, DeviceStatus

T = TypeVar("T")


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
    user_id: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SensorUpdate(BaseModel):
    sensor_type: Optional[str] = None
    units_of_measure: Optional[str] = None
    max_value: Optional[float] = None
    min_value: Optional[float] = None


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
    user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    

class ActuatorUpdate(BaseModel):
    current_state: Optional[ActuatorState] = None
    actuator_type: Optional[str] = None
    available_states: Optional[dict] = None
    user_id: Optional[str] = None
    device_id: Optional[str] = None


class ActuatorCreate(ActuatorBase):
    device_id: str


# Device Models

class DeviceBase(BaseModel):
    unique_device_id: str
    device_ip_address: str
    model_number: str
    firmware_version: str


class DeviceCreate(DeviceBase):
    sensors_list: Optional[List[SensorBase]] = None
    actuators_list: Optional[List[ActuatorBase]] = None


class DeviceRead(DeviceBase):
    device_id: str
    user_id: Optional[str] = None
    farm_id: Optional[str] = None
    created_at: datetime
    sensors: List[SensorRead]
    actuators: List[ActuatorRead]
    model_config = ConfigDict(from_attributes=True)


class DeviceUpdate(BaseModel):
    device_ip_address: Optional[str] = None
    model_number: Optional[str] = None
    firmware_version: Optional[str] = None
    status: Optional[DeviceStatus] = None

    # Allows assigning a device to a new user or farm later
    user_id: Optional[str] = None
    farm_id: Optional[str] = None


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
    farm_name: Optional[str] = None
    total_area: Optional[int] = None
    location: Optional[str] = None



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
    planting_date: Optional[date] = None
    expected_harvest_date: Optional[date] = None
    current_grow_stage: Optional[str] = None


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
    details: Optional[Any] = None


class CursorPagination(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: Optional[str] = None


DevicePagination = CursorPagination[DeviceRead]
SensorPagination = CursorPagination[SensorRead]
ActuatorPagination = CursorPagination[ActuatorRead]
FarmPagination = CursorPagination[FarmRead]
CropManagmentPagination = CursorPagination[CropManagmentRead]
CropTypesPagination = CursorPagination[CropRead]