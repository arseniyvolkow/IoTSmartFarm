from typing import Annotated
from fastapi import Depends, Request
# Импортируем классы сервисов
from sensor_data_service.services.redis_service import RedisService
from sensor_data_service.services.Influxdb_service import InfluxDBService
from sensor_data_service.services.mqtt_service import AsyncMQTTService
from sensor_data_service.database import Settings

# --- Вспомогательные функции получения из state ---
# Они достают уже инициализированные в lifespan сервисы

def get_settings(request: Request) -> Settings:
    return request.app.state.settings

def get_influx_service(request: Request) -> InfluxDBService:
    return request.app.state.influx_service

def get_mqtt_service(request: Request) -> AsyncMQTTService:
    return request.app.state.mqtt_service

def get_redis_service(request: Request) -> RedisService:
    return request.app.state.redis_service

# --- Типизированные зависимости (Dependency Injection) ---

InfluxServiceDependency = Annotated[InfluxDBService, Depends(get_influx_service)]
MQTTServiceDependency = Annotated[AsyncMQTTService, Depends(get_mqtt_service)]
RedisServiceDependency = Annotated[RedisService, Depends(get_redis_service)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]