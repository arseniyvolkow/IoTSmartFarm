import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status

# Импорты безопасности (Из Common Lib)
from common.auth.security import CheckAccess

# Импорты зависимостей (Наш новый файл)
from sensor_data_service.dependencies import (
    InfluxServiceDependency,
    MQTTServiceDependency,
    RedisServiceDependency,
)

# Импорты схем
from sensor_data_service.schemas import ActuatorPayload, SensorDataBatch

router = APIRouter(tags=["Sensor Data"])
logger = logging.getLogger(__name__)

# --- Endpoints ---


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check(
    influx_service: InfluxServiceDependency,
    mqtt_service: MQTTServiceDependency,
    redis_service: RedisServiceDependency,
):
    """Check the health of all services"""
    try:
        mqtt_status = "connected" if mqtt_service.is_connected() else "disconnected"
        redis_status = "connected" if redis_service.is_connected() else "disconnected"
        influxdb_connected = await influx_service.ping()
        influxdb_status = "connected" if influxdb_connected else "disconnected"
        return {
            "status": "running",
            "mqtt_status": mqtt_status,
            "influxdb_status": influxdb_status,
            "redis_status": redis_status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e!s}")


@router.post(
    "/simulate-sensor-data",
    status_code=status.HTTP_201_CREATED,
    # ЗАЩИТА: Только для тех, кто может писать данные сенсоров (или Админы)
    dependencies=[Depends(CheckAccess("sensors", "write"))],
)
async def simulate_sensor_data(
    data_batch: SensorDataBatch,
    influx_service: InfluxServiceDependency,
    redis_service: RedisServiceDependency,
):
    """
    Simulate sensor data. Protected by RBAC.
    """
    try:
        sensor_data_list = [reading.model_dump() for reading in data_batch.sensors]

        await asyncio.gather(
            influx_service.save_sensor_data(sensor_data_list),
            redis_service.update_cache_from_batch(sensor_data_list),
        )

        return {
            "status": "success",
            "readings_processed": len(sensor_data_list),
        }
    except Exception as e:
        logger.error(f"Error processing simulated batch data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/sensor-value/{sensor_id}",
    # ЗАЩИТА: Чтение сенсоров
    dependencies=[Depends(CheckAccess("sensors", "read"))],
)
async def get_sensor_value(
    sensor_id: str,
    redis_service: RedisServiceDependency,
):
    """Get cached sensor value."""
    try:
        value = await redis_service.get_sensor_value(sensor_id)
        if value is None:
            raise HTTPException(
                status_code=404, detail="Sensor value not found in cache"
            )
        return {"sensor_id": sensor_id, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sensor-data/{sensor_id}/{time}",
    # ЗАЩИТА: Чтение сенсоров
    dependencies=[Depends(CheckAccess("sensors", "read"))],
)
async def get_timeseries_data_by_id(
    sensor_id: str,
    time: str,
    influx_service: InfluxServiceDependency,
    redis_service: RedisServiceDependency,
):
    """Get historical data with Redis caching."""
    try:
        # 1. Try to get from Cache first
        cached_data = await redis_service.get_cached_history(sensor_id, time)
        if cached_data:
            logger.debug(f"Serving history for {sensor_id} from cache")
            return {
                "status": "success",
                "sensor_id": sensor_id,
                "data": cached_data,
                "cached": True,
            }

        # 2. Cache miss: Query InfluxDB
        data_points = await influx_service.query_data_by_sensor_id(
            sensor_id=sensor_id, time_range=time
        )

        if not data_points:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for sensor_id '{sensor_id}'.",
            )

        # 3. Save to cache for 15 seconds to prevent DB hammering
        await redis_service.set_cached_history(sensor_id, time, data_points, ttl=15)

        return {
            "status": "success",
            "sensor_id": sensor_id,
            "data": data_points,
            "cached": False,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error querying historical data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/actuator-mode-update",
    status_code=status.HTTP_202_ACCEPTED,
    # ЗАЩИТА: Управление актуаторами (отдельный ресурс или тот же sensors:write)
    dependencies=[Depends(CheckAccess("actuators", "write"))],
)
async def actuator_mode_update(
    action_payload: ActuatorPayload,
    mqtt_service: MQTTServiceDependency,
):
    try:
        tasks = []
        for actuator in action_payload.actuators_to_control:
            topic = f"actuator/{actuator.actuator_id}/command"
            tasks.append(mqtt_service.publish_mqtt_message(topic, actuator.command))

        if tasks:
            await asyncio.gather(*tasks)

    except Exception as e:
        logger.exception(f"Error updating actuators: {e}")
        raise HTTPException(status_code=500, detail=str(e))
