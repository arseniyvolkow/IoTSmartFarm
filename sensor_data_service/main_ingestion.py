import asyncio
import logging
import os
import sys
from sensor_data_service.database import Settings
from sensor_data_service.services.redis_service import RedisService
from sensor_data_service.services.Influxdb_service import InfluxDBService
from sensor_data_service.services.mqtt_service import AsyncMQTTService

# Clean production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def main():
    settings = Settings()
    
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
    
    try:
        await redis_service.connect()
        logger.info("Redis connection successful.")

        await influx_service.__aenter__()
        logger.info("InfluxDB Service initialized.")

        unique_client_id = f"sensor_ingestion_worker_{os.getpid()}"

        mqtt_service = AsyncMQTTService(
            broker=settings.MQTT_BROKER,
            port=settings.MQTT_PORT,
            username=settings.MQTT_USERNAME,
            password=settings.MQTT_PASSWORD,
            influx_service=influx_service,
            redis_service=redis_service,
            client_id=unique_client_id
        )
        
        # Start in 'ingestion' mode
        await mqtt_service.start(mode="ingestion")
        logger.info(f"Async MQTT Service started in INGESTION mode.")
        
        # Keep the worker running
        while True:
            await asyncio.sleep(3600)
            
    except asyncio.CancelledError:
        logger.info("Ingestion worker cancelled.")
    except Exception as e:
        logger.error(f"Error in ingestion worker: {e}")
    finally:
        await mqtt_service.stop()
        await influx_service.__aexit__(None, None, None)
        await redis_service.disconnect()
        logger.info("Ingestion worker cleanly shutdown.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass