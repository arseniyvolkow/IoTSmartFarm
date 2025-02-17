from .database import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Enum, Integer, Float,Date, String, ForeignKey
import uuid

def generate_uuid():
    return str(uuid.uuid4())


class Crops(Base):
    __tablename__ = 'crops'

    crop_id = Column(String, primary_key=True, default=generate_uuid)
    crop_name = Column(String, unique=True)

    crop_management_entries = relationship("Crop_managment", back_populates="crop_type")
    

class Farms(Base):
    __tablename__ = 'farms'

    farm_id = Column(String, primary_key=True, default=generate_uuid)
    farm_name = Column(String)
    total_area = Column(Integer)
    owner_id = Column(String)
    location = Column(String)
    crop = Column(String, ForeignKey('CropManagement.crop_id'))

    devices = relationship("Devices", back_populates="farm")
    crop_managment = relationship("Crop_managment", back_populates="farm")
    

class CropManagement(Base):
    __tablename__ = 'CropManagement'

    crop_id = Column(String, primary_key=True, default=generate_uuid)
    planting_date = Column(Date)
    owner_id = Column(String)
    expected_harvest_date = Column(Date)
    current_grow_stage = Column(String)
    crop_type_id = Column(String, ForeignKey('crops.crop_id'))

    crop_type = relationship("Crops", back_populates="crop_management_entries") 
    farm = relationship("Farms", back_populates="CropManagement")


class Devices(Base):
    __tablename__ = 'devices'
    
    unique_device_id = Column(String, primary_key=True)
    device_ip_address = Column(String)
    user_id = Column(String)
    farm_id = Column(String,ForeignKey('farms.farm_id'))
    installation_date = Column(Date)
    model_number = Column(String)
    firmware_version = Column(String)
    status = Column(Enum('active', 'inactive', 'maintenance', name='device_status'), default='active')

    farm = relationship("Farms", back_populates="devices")
    sensors = relationship("Sensors", back_populates="device")

class Sensors(Base):
    __tablename__ = 'sensors'

    sensor_id = Column(String, primary_key=True, default=generate_uuid)
    device_id = Column(String, ForeignKey("devices.unique_device_id"))
    sensor_type = Column(String)
    units_of_measure = Column(String)
    max_value = Column(Float)
    min_value = Column(Float)

    device = relationship("Devices", back_populates="sensors")

class Alerts(Base):
    __tablename__ = 'alerts'

    alert_id = Column(String, primary_key=True, default=generate_uuid)
    farm_id = Column(String, ForeignKey('farms.farm_id'))
    device_id = Column(String, ForeignKey('devices.unique_device_id'))
    alert_type = Column(String)
