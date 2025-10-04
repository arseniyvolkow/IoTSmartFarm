from fastapi import FastAPI, HTTPException, Depends, Request, status
from .database import Settings, AsyncMQTTService, InfluxDBService, RedisService
import redis.exceptions
from .schemas import ActuatorControl, ActuatorPayload, SensorDataBatch, SensorReading
import logging
import asyncio


logger = logging.getLogger(__name__)


async def lifespan(app: FastAPI):
    """Application lifespan management"""
    settings = Settings()
    influx_service = InfluxDBService(
        url=settings.INFLUXDB_URL,
        token=settings.INFLUXDB_TOKEN,
        org=settings.INFLUXDB_ORG,
        bucket=settings.INFLUXDB_BUCKET,
    )
    redis_service = RedisService(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD
    )
    try:
        await redis_service.connect()
        print("Redis connection successful.")

        await influx_service.__aenter__()
        print("InfluxDB Service initialized.")

        mqtt_service = AsyncMQTTService(
            broker=settings.MQTT_BROKER,
            port=settings.MQTT_PORT,
            username=settings.MQTT_USERNAME,
            password=settings.MQTT_PASSWORD,
            influx_service=influx_service,
            redis_service=redis_service,
        )
        await mqtt_service.start()
        print("Async MQTT Service started.")

        app.state.influx_service = influx_service
        app.state.mqtt_service = mqtt_service
        app.state.redis_service = redis_service
        app.state.settings = settings
        yield
    except Exception as e:
        print(f"Error during startup: {e}")
        raise
    finally:
        try:
            if "mqtt_service" in app.state:
                await app.state.mqtt_service.stop()
                print("Async MQTT service stopped.")
            if "influx_service" in app.state:
                await app.state.influx_service.__aexit__(None, None, None)
                print("InfluxDB service closed.")
            if "redis_service" in app.state:
                await app.state.redis_service.disconnect()
                print("Redis service disconnected.")
            print("All services stopped and connections closed.")
        except Exception as e:
            print(f"Error during cleanup: {e}")


app = FastAPI(lifespan=lifespan, root_path="/api/sensor-data")


def get_influx_service(request: Request) -> InfluxDBService:
    return request.app.state.influx_service


def get_mqtt_service(request: Request) -> AsyncMQTTService:
    return request.app.state.mqtt_service


def get_redis_service(request: Request) -> RedisService:
    return request.app.state.redis_service


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(
    influx_service: InfluxDBService = Depends(get_influx_service),
    mqtt_service: AsyncMQTTService = Depends(get_mqtt_service),
    redis_service: RedisService = Depends(get_redis_service),
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
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@app.post("/simulate-sensor-data", status_code=status.HTTP_201_CREATED)
async def simulate_sensor_data(
    data_batch: SensorDataBatch,
    influx_service: InfluxDBService = Depends(get_influx_service),
    redis_service: RedisService = Depends(get_redis_service),
):
    """
    Simulate sensor data by saving to InfluxDB and updating the Redis cache using sensor_id.
    """
    try:
        sensor_data_list = [reading.model_dump() for reading in data_batch.sensors]

        # Concurrently save to InfluxDB and update Redis cache
        await asyncio.gather(
            influx_service.save_sensor_data(sensor_data_list),
            redis_service.update_cache_from_batch(sensor_data_list),  # MODIFIED
        )

        return {
            "status": "batch data saved to InfluxDB and Redis cache updated",
            "readings_processed": len(sensor_data_list),
        }
    except Exception as e:
        logger.error(f"Error processing simulated batch data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing simulated batch data: {str(e)}",
        )


@app.get("/sensor-value/{device_id}/{sensor_id}")
async def get_sensor_value(
    device_id: str,
    sensor_id: str,
    redis_service: RedisService = Depends(get_redis_service),
):
    """Get cached sensor value from Redis"""
    try:
        sensor_key = f"{device_id}:{sensor_id}"
        value = await redis_service.get_sensor_value(sensor_key)
        if value is None:
            raise HTTPException(status_code=404, detail="Sensor value not found")
        return {"device_id": device_id, "sensor_id": sensor_id, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving sensor value: {str(e)}"
        )


# MODIFIED: Changed route, function name, and logic to remove device_id
@app.get("/sensor_data/{sensor_type}/{time}")
async def get_timeseries_data(
    sensor_type: str,
    time: str,
    influx_service: InfluxDBService = Depends(get_influx_service),
):
    """Get time series data for a specific sensor type"""
    try:
        # MODIFIED: Called the renamed method without device_id
        data_points = await influx_service.query_sensor_data(
            sensor_type=sensor_type, time_range=time
        )
        return {
            "status": "success",
            "sensor_type": sensor_type,
            "time_range": time,
            "data_points": len(data_points),
            "data": data_points,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error querying InfluxDB: {str(e)}"
        )


# MODIFIED: Changed route, function name, and logic to remove device_id
@app.get("/all_sensor_data/{time}")
async def get_all_sensors_data(
    time: str,
    influx_service: InfluxDBService = Depends(get_influx_service),
):
    """Get time series data for all sensors"""
    try:
        # MODIFIED: Called the renamed method without device_id
        data_points = await influx_service.query_all_sensors(time_range=time)
        sensors_data = {}
        for point in data_points:
            sensor_type = point["sensor_type"]
            if sensor_type not in sensors_data:
                sensors_data[sensor_type] = []
            sensors_data[sensor_type].append(point)
        return {
            "status": "success",
            "time_range": time,
            "total_data_points": len(data_points),
            "sensors": list(sensors_data.keys()),
            "data": sensors_data,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error querying InfluxDB: {str(e)}"
        )


# MODIFIED: Changed route, function name, and logic to remove device_id
@app.get("/latest_sensor_data")
async def get_latest_values(
    influx_service: InfluxDBService = Depends(get_influx_service),
):
    """Get the latest values for all sensors"""
    try:
        # MODIFIED: Called the renamed method without device_id
        latest_values = await influx_service.get_latest_sensor_values()
        if not latest_values:
            raise HTTPException(status_code=404, detail="No sensor data found")
        return {
            "status": "success",
            "sensors_count": len(latest_values),
            "data": latest_values,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error querying latest values: {str(e)}"
        )


@app.post("/actuator-mode-update", status_code=status.HTTP_202_ACCEPTED)
async def actuator_mode_update(
    action_payload: ActuatorPayload,
    mqtt_service: AsyncMQTTService = Depends(get_mqtt_service),
):
    try:
        for actuator in action_payload.actuators_to_control:
            actuator_id = actuator.actuator_id
            command = actuator.command
            topic = f"actuator/{actuator_id}/command"
            await mqtt_service.publish_mqtt_message(topic, command)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error during publishing: {str(e)}"
        )
