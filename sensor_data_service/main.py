import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, Request
import aiomqtt

from .database import Settings, InfluxDBService
from .services import SensorDataHandler

# --- Lifespan Management ---


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Handles application startup and shutdown events.
    Manages InfluxDB and MQTT client connections and a background listener task.
    """
    print("Application starting up...")
    settings = Settings()

    async with InfluxDBService(
        url=settings.INFLUXDB_URL,
        token=settings.INFLUXDB_TOKEN,
        org=settings.INFLUXDB_ORG,
        bucket=settings.INFLUXDB_BUCKET,
    ) as influx_service:
        app.state.influx_service = influx_service
        handler = SensorDataHandler(influx_service)

        async with aiomqtt.Client(
            hostname=settings.MQTT_BROKER,
            port=settings.MQTT_PORT,
            username=settings.MQTT_USERNAME,
            password=settings.MQTT_PASSWORD,
        ) as mqtt_client:
            app.state.mqtt_client = mqtt_client
            print("MQTT Client Connected.")
            mqtt_listener_task = asyncio.create_task(listen_mqtt(mqtt_client, handler))
            yield
            print("Application shutting down...")
            mqtt_listener_task.cancel()
            try:
                await mqtt_listener_task
            except asyncio.CancelledError:
                print("MQTT listener task successfully cancelled.")


async def listen_mqtt(client: aiomqtt.Client, handler: SensorDataHandler):
    """Listens for messages on the subscribed topic and processes them."""
    await client.subscribe("device/+/data")
    print("Subscribed to MQTT topic 'device/+/data'")
    try:
        async for message in client.messages:
            await handler.handle_message(message.topic.value, message.payload)
    except asyncio.CancelledError:
        print("MQTT listener stopped.")
        raise
    except Exception as e:
        print(f"An error occurred in the MQTT listener: {e}")


# --- FastAPI App and Dependency Injection ---

app = FastAPI(lifespan=lifespan, root_path="/api/sensor-data")


def get_influx_service(request: Request) -> InfluxDBService:
    return request.app.state.influx_service


def get_mqtt_client(request: Request) -> aiomqtt.Client:
    return request.app.state.mqtt_client


# --- API Endpoints ---


@app.get("/health")
async def health_check(
    influx_service: InfluxDBService = Depends(get_influx_service),
    mqtt_client: aiomqtt.Client = Depends(get_mqtt_client),
):
    """Provides the health status of the application and its services."""
    influx_ok = await influx_service.ping()
    return {
        "status": "running",
        "mqtt_status": "connected" if mqtt_client.is_connected else "disconnected",
        "influxdb_status": "connected" if influx_ok else "disconnected",
    }


@app.post("/simulate-sensor-data")
async def simulate_sensor_data(
    device_id: str,
    sensor_id: str,
    sensor_type: str,
    value: float,
    influx_service: InfluxDBService = Depends(get_influx_service),
):
    """Endpoint to simulate and directly save a single sensor reading."""
    sensor_data_as_list = [
        {"sensor_id": sensor_id, "sensor_type": sensor_type, "value": value}
    ]
    await influx_service.save_sensor_data(device_id, sensor_data_as_list)
    return {
        "status": "simulated data saved",
        "device_id": device_id,
        "data": sensor_data_as_list,
    }


@app.get("/device_data/{device_id}/{sensor_type}/{time_range}")
async def get_timeseries_data_for_device(
    device_id: str,
    sensor_type: str,
    time_range: str,
    influx_service: InfluxDBService = Depends(get_influx_service),
):
    """
    Retrieves time-series data for a specific device and sensor type.
    'time_range' can be '1h', '24h', '7d', or '30d'.
    """
    valid_times = {"1h": "-1h", "24h": "-24h", "7d": "-7d", "30d": "-30d"}
    if time_range not in valid_times:
        raise HTTPException(
            status_code=400, detail="Invalid time_range. Use: 1h, 24h, 7d, or 30d"
        )

    # Use parameterized query to prevent Flux injection
    flux_query = """
        from(bucket: params.bucketName)
            |> range(start: v.timeRange)
            |> filter(fn: (r) => r._measurement == "sensor_data")
            |> filter(fn: (r) => r.device_id == params.deviceID)
            |> filter(fn: (r) => r.sensor_type == params.sensorType)
            |> sort(columns: ["_time"])
    """
    query_params = {
        "bucketName": influx_service.bucket,
        "timeRange": valid_times[time_range],
        "deviceID": device_id,
        "sensorType": sensor_type,
    }

    try:
        result = await influx_service.query_data(flux_query, params=query_params)
        data = [
            {"time": record.get_time(), "value": record.get_value()}
            for table in result
            for record in table.records
        ]
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying data: {str(e)}")
