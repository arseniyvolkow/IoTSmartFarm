import logging
from fastapi import FastAPI
from sensor_data_service.database import Settings
from sensor_data_service.services.redis_service import RedisService
from sensor_data_service.services.Influxdb_service import InfluxDBService
from sensor_data_service.services.mqtt_service import AsyncMQTTService
from sensor_data_service.routers import sensors

logger = logging.getLogger(__name__)

async def lifespan(app: FastAPI):
    """Application lifespan management: Init services"""
    settings = Settings()
    
    # 1. Init Services
    influx_service = InfluxDBService(
        url=settings.INFLUXDB_URL,
        token=settings.INFLUXDB_TOKEN,
        org=settings.INFLUXDB_ORG,
        bucket=settings.INFLUXDB_BUCKET,
    )
    redis_service = RedisService(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
    )
    
    # 2. Connect & Start
    try:
        await redis_service.connect()
        logger.info("Redis connection successful.")

        await influx_service.__aenter__()
        logger.info("InfluxDB Service initialized.")

        mqtt_service = AsyncMQTTService(
            broker=settings.MQTT_BROKER,
            port=settings.MQTT_PORT,
            username=settings.MQTT_USERNAME,
            password=settings.MQTT_PASSWORD,
            influx_service=influx_service,
            redis_service=redis_service,
        )
        await mqtt_service.start()
        logger.info("Async MQTT Service started.")

        # 3. Store in State
        app.state.influx_service = influx_service
        app.state.mqtt_service = mqtt_service
        app.state.redis_service = redis_service
        app.state.settings = settings
        
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # 4. Cleanup
        if hasattr(app.state, "mqtt_service"):
            await app.state.mqtt_service.stop()
        if hasattr(app.state, "influx_service"):
            await app.state.influx_service.__aexit__(None, None, None)
        if hasattr(app.state, "redis_service"):
            await app.state.redis_service.disconnect()
        logger.info("All services stopped.")

app = FastAPI(lifespan=lifespan, root_path="/api/sensor-data")


app.include_router(sensors.router)