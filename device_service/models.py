from .database import Base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Enum, ForeignKey, DateTime, Text, JSON
from typing import List, Optional
import uuid
from sqlalchemy.sql import func
from datetime import datetime, date
from enum import Enum as PyEnum


class ActuatorState(PyEnum):
    ON = "on"
    OFF = "off"
    PAUSED = "paused"
    ERROR = "error"
    IDLE = "idle"


class DeviceStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


def generate_uuid():
    return str(uuid.uuid4())


class Crops(Base):
    __tablename__ = "crops"
    crop_id: Mapped[str] = mapped_column(primary_key=True, default=generate_uuid)
    crop_name: Mapped[str] = mapped_column(unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    crop_management_entries: Mapped[List["CropManagment"]] = relationship(
        back_populates="crop_type"
    )


class Farms(Base):
    __tablename__ = "farms"

    farm_id: Mapped[str] = mapped_column(primary_key=True, default=generate_uuid)
    farm_name: Mapped[str]
    total_area: Mapped[int]
    user_id: Mapped[str] = mapped_column(index=True)
    location: Mapped[str]
    crop_id: Mapped[str] = mapped_column(
        ForeignKey("CropManagement.crop_id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    devices: Mapped[List["Devices"]] = relationship(back_populates="farm")
    crop_management_entries: Mapped[List["CropManagment"]] = relationship(
        "CropManagment", back_populates="farm"
    )
    alerts: Mapped[List["Alerts"]] = relationship("Alerts", back_populates="farm_rel")


class CropManagment(Base):
    __tablename__ = "CropManagement"
    crop_id: Mapped[str] = mapped_column(primary_key=True, default=generate_uuid)
    planting_date: Mapped[date]
    user_id: Mapped[str] = mapped_column(index=True)
    expected_harvest_date: Mapped[date]
    current_grow_stage: Mapped[str]
    crop_type_id: Mapped[str] = mapped_column(ForeignKey("crops.crop_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    crop_type: Mapped[List["Crops"]] = relationship(
        "Crops", back_populates="crop_management_entries"
    )
    farm: Mapped[List["Farms"]] = relationship(
        "Farms", back_populates="crop_management_entries"
    )


class Devices(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(index=True, primary_key=True, default=generate_uuid)
    unique_device_id: Mapped[str] = mapped_column(index=True)
    device_ip_address: Mapped[str]
    user_id: Mapped[str] = mapped_column(index=True,  nullable=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.farm_id"), index=True,  nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    model_number: Mapped[str]
    firmware_version: Mapped[str]

    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="device_status", create_type=True),
        default=DeviceStatus.ACTIVE,
    )
    farm: Mapped[List[Farms]] = relationship("Farms", back_populates="devices")
    sensors: Mapped[List["Sensors"]] = relationship("Sensors", back_populates="device")
    actuators: Mapped[List["Actuators"]] = relationship(
        "Actuators", back_populates="device"
    )
    alerts: Mapped[List["Alerts"]] = relationship("Alerts", back_populates="device_rel")


# New Model for Actuators
class Actuators(Base):
    __tablename__ = "actuators"

    actuator_id: Mapped[str] = mapped_column(primary_key=True, default=generate_uuid)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.device_id"), index=True
    )
    user_id: Mapped[str] = mapped_column(index=True,  nullable=True)
    actuator_type: Mapped[str] = mapped_column(Text)
    current_state: Mapped[ActuatorState] = mapped_column(
        Enum(ActuatorState, name="actuator_state", create_type=True),
        default=ActuatorState.OFF,
    )
    available_states: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=lambda: {}
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship back to the device
    device: Mapped["Devices"] = relationship(back_populates="actuators")

    # Correct relationship to the Alerts model
    alerts: Mapped[List["Alerts"]] = relationship(
        "Alerts", back_populates="actuator_rel"
    )


class Sensors(Base):
    __tablename__ = "sensors"

    sensor_id: Mapped[str] = mapped_column(primary_key=True, default=generate_uuid)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.device_id"), index=True
    )
    user_id: Mapped[str] = mapped_column(index=True,  nullable=True)
    sensor_type: Mapped[str]
    units_of_measure: Mapped[str]
    max_value: Mapped[float]
    min_value: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    device: Mapped[list["Devices"]] = relationship("Devices", back_populates="sensors")


class Alerts(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(primary_key=True, default=generate_uuid)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.farm_id"), index=True)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.device_id"), index=True
    )

    # Correct Foreign Key to the Actuators table
    actuator_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("actuators.actuator_id"), nullable=True
    )

    alert_type: Mapped[str]
    message: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by_rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_value: Mapped[float] = mapped_column(nullable=True)
    is_resolved: Mapped[bool] = mapped_column(default=False)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship back to the Actuators model
    actuator_rel: Mapped["Actuators"] = relationship(
        "Actuators", back_populates="alerts"
    )

    # Relationships to Farms and Devices
    farm_rel: Mapped["Farms"] = relationship(
        "Farms", foreign_keys=[farm_id], back_populates="alerts"
    )
    device_rel: Mapped["Devices"] = relationship(
        "Devices", foreign_keys=[device_id], back_populates="alerts"
    )
