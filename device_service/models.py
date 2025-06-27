from .database import Base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Enum, ForeignKey, DateTime, Index # Import Index
from typing import List
import uuid
from sqlalchemy.sql import func
from datetime import datetime, date
from enum import Enum as PyEnum


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
    crop_id: Mapped[str] = mapped_column(ForeignKey("CropManagement.crop_id"), index=True) 
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    devices: Mapped[List["Devices"]] = relationship(back_populates="farm")
    crop_managment: Mapped[List["CropManagment"]] = relationship(
        "CropManagment", back_populates="farm"
    )


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
    farm: Mapped[List["Farms"]] = relationship("Farms", back_populates="CropManagement")


class Devices(Base):
    __tablename__ = "devices"

    unique_device_id: Mapped[str] = mapped_column(primary_key=True)
    device_ip_address: Mapped[str]
    user_id: Mapped[str] = mapped_column(index=True) 
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.farm_id"), index=True) 
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


class Sensors(Base):
    __tablename__ = "sensors"

    sensor_id: Mapped[str] = mapped_column(primary_key=True, default=generate_uuid)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.unique_device_id"), index=True)
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
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.unique_device_id"), index=True) 
    alert_type: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
