from typing import Any, Optional
from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional, List, TypeVar, Generic
from enum import Enum as PyEnum


T = TypeVar("T")


# Device Models
class ActuatorState(PyEnum):
    ON = "on"
    OFF = "off"
    PAUSED = "paused"
    ERROR = "error"
    IDLE = "idle"


class SensorBase(BaseModel):
    """Base model for shared sensor fields."""

    sensor_type: str
    units_of_measure: str
    max_value: float
    min_value: float


class SensorRead(SensorBase):
    """Model for reading a sensor from the database."""

    sensor_id: str
    device_id: str
    created_at: datetime

    # This setting is necessary for SQLAlchemy ORM compatibility
    model_config = ConfigDict(from_attributes=True)


class ActuatorBase(BaseModel):
    actuator_type: str
    current_state: ActuatorState
    available_states: dict


class ActuatorRead(ActuatorBase):
    actuator_id: str
    device_id: str
    created_at: datetime
    updated_at: datetime

    # This setting is necessary for SQLAlchemy ORM compatibility
    model_config = ConfigDict(from_attributes=True)


class AddNewDevice(BaseModel):
    unique_device_id: str
    device_ip_address: str
    model_number: str
    firmware_version: str
    sensors_list: Optional[List[SensorBase]] = None
    actuators_list: Optional[List[ActuatorBase]] = None


class UpdateDeviceInfo(BaseModel):
    status: str


class DeviceSchema(BaseModel):
    device_id: str
    unique_device_id: str
    user_id: Optional[str] = None
    farm_id: Optional[str] = None
    device_ip_address: str
    model_number: str
    firmware_version: str
    status: str


# Farms models


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


# Error


class ErrorResponse(BaseModel):
    message: str
    details: Optional[Any] = None


class CursorPagination(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: Optional[str] = None


DevicePagination = CursorPagination[DeviceSchema]
FarmPagination = CursorPagination[FarmModel]
ActuatorPagination = CursorPagination[ActuatorBase]