from fastapi import FastAPI, HTTPException, Depends, Request, status
from .database import Settings, AsyncMQTTService, InfluxDBService, RedisService
import redis.exceptions
from .schemas import ActuatorControl, ActuatorPayload

async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # 1. Initialize settings
    settings = Settings()

    # 2. Initialize data services
    influx_service = InfluxDBService(
        url=settings.INFLUXDB_URL,
        token=settings.INFLUXDB_TOKEN,
        org=settings.INFLUXDB_ORG,
        bucket=settings.INFLUXDB_BUCKET,
    )

    redis_service = RedisService(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB
    )

    try:
        # Connect to Redis
        await redis_service.connect()
        print("Redis connection successful.")

        # Initialize InfluxDB service
        await influx_service.__aenter__() 
        print("InfluxDB Service initialized.")

        # Initialize and start async MQTT service
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

        # Store services in application state
        app.state.influx_service = influx_service
        app.state.mqtt_service = mqtt_service
        app.state.redis_service = redis_service
        app.state.settings = settings

        yield  # App will run while this generator yields

    except Exception as e:
        print(f"Error during startup: {e}")
        raise
    finally:
        # Cleanup services
        try:
            if "mqtt_service" in locals():
                await mqtt_service.stop()
                print("Async MQTT service stopped.")
            if "influx_service" in locals():
                await influx_service.__aexit__(None, None, None)
                print("InfluxDB service closed.")
            if "redis_service" in locals():
                await redis_service.disconnect()
                print("Redis service disconnected.")
            print("All services stopped and connections closed.")
        except Exception as e:
            print(f"Error during cleanup: {e}")


# FastAPI application
app = FastAPI(lifespan=lifespan, root_path="/api/sensor-data")


# Dependency functions
def get_influx_service(request: Request) -> InfluxDBService:
    return request.app.state.influx_service


def get_mqtt_service(request: Request) -> AsyncMQTTService:
    return request.app.state.mqtt_service


def get_redis_service(request: Request) -> RedisService:
    return request.app.state.redis_service


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


# Health check endpoint
@app.get("/health")
async def health_check(
    influx_service: InfluxDBService = Depends(get_influx_service),
    mqtt_service: AsyncMQTTService = Depends(get_mqtt_service),
    redis_service: RedisService = Depends(get_redis_service),
):
    """Check the health of all services"""
    try:
        mqtt_status = "connected" if mqtt_service.is_connected() else "disconnected"
        redis_status = "connected" if redis_service.is_connected() else "disconnected"

        # Check InfluxDB connection using the new ping method
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


# Simulate sensor data endpoint
@app.post("/simulate-sensor-data")
async def simulate_sensor_data(
    device_id: str,
    sensor_key: str,
    value: float,
    influx_service: InfluxDBService = Depends(get_influx_service),
):
    """Simulate sensor data by directly saving to InfluxDB"""
    try:
        sensor_data_list = [
            {"sensor_id": sensor_key, "sensor_type": sensor_key, "value": value}
        ]

        await influx_service.save_sensor_data(device_id, sensor_data_list)
        return {
            "status": "simulated data saved",
            "device_id": device_id,
            "data": sensor_data_list,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error saving simulated data: {str(e)}"
        )


# Get sensor value from Redis
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


# Get time series data for specific device and sensor type
@app.get("/device_data/{device_id}/{sensor_type}/{time}")
async def get_timeseries_data_for_device(
    device_id: str,
    sensor_type: str,
    time: str,
    influx_service: InfluxDBService = Depends(get_influx_service),
):
    """Get time series data for a specific device and sensor type"""
    try:
        data_points = await influx_service.query_device_sensor_data(
            device_id=device_id, sensor_type=sensor_type, time_range=time
        )

        return {
            "status": "success",
            "device_id": device_id,
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


# Get all sensor data for a device
@app.get("/device_data/{device_id}/{time}")
async def get_all_device_data(
    device_id: str,
    time: str,
    influx_service: InfluxDBService = Depends(get_influx_service),
):
    """Get time series data for all sensors of a specific device"""
    try:
        data_points = await influx_service.query_device_all_sensors(
            device_id=device_id, time_range=time
        )

        # Group data by sensor type for better organization
        sensors_data = {}
        for point in data_points:
            sensor_type = point["sensor_type"]
            if sensor_type not in sensors_data:
                sensors_data[sensor_type] = []
            sensors_data[sensor_type].append(point)

        return {
            "status": "success",
            "device_id": device_id,
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


# Get latest sensor values for a device
@app.get("/device/{device_id}/latest")
async def get_latest_device_values(
    device_id: str,
    influx_service: InfluxDBService = Depends(get_influx_service),
):
    """Get the latest values for all sensors of a device"""
    try:
        latest_values = await influx_service.get_latest_sensor_values(device_id)

        if not latest_values:
            raise HTTPException(status_code=404, detail="No data found for this device")

        return {
            "status": "success",
            "device_id": device_id,
            "sensors_count": len(latest_values),
            "data": latest_values,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error querying latest values: {str(e)}"
        )


@app.post('/actuator-mode-update', status_code=status.HTTP_202_ACCEPTED)
async def actuator_mode_update(
    action_payload: ActuatorPayload, 
    mqtt_service: AsyncMQTTService = Depends(get_mqtt_service)
):
    try:
        for actuator in action_payload.actuators_to_control:
            actuator_id = actuator.actuator_id
            command = actuator.command
            topic = f"actuator/{actuator_id}/command"
            await mqtt_service.publish_mqtt_message(topic, command)  # Add await!
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error during publishing: {str(e)}"  # Fix typo
        )