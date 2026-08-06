import asyncio
import json
import logging
import os
import sys

from sensor_data_service.database import Settings
from sensor_data_service.services.Influxdb_service import InfluxDBService
from sensor_data_service.services.mqtt_service import AsyncMQTTService
from sensor_data_service.services.redis_service import RedisService

# Clean production logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def actuator_command_subscriber(
    redis_service: RedisService, mqtt_service: AsyncMQTTService
):
    """Listens to Redis 'actuator_commands' channel and forwards to MQTT."""
    if not redis_service.client:
        return
    pubsub = redis_service.client.pubsub()
    await pubsub.subscribe("actuator_commands")
    logger.info("📡 Subscribed to Redis channel 'actuator_commands'")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    actuators = payload.get("actuators_to_control", [])
                    for act in actuators:
                        device_id = act.get("device_id")
                        if not device_id:
                            logger.warning(
                                f"⚠️ Skipping actuator command due to missing device_id: {act}"
                            )
                            continue

                        topic = f"device/{device_id}/commands"
                        # Forward as JSON to edge device
                        mqtt_payload = json.dumps(
                            {
                                "command": "control_actuator",
                                "actuator_id": act.get("actuator_id"),
                                "action": act,
                            }
                        )

                        # 1. Update the Twin's desired state in Redis
                        await redis_service.update_desired_state(
                            device_id, {act.get("actuator_id"): act}
                        )

                        # 2. QoS 1 guarantees at least once delivery
                        if mqtt_service.client:
                            await mqtt_service.client.publish(
                                topic, payload=mqtt_payload, qos=1
                            )
                            logger.info(
                                f"📤 Forwarded actuator command to MQTT and saved Twin: {topic}"
                            )
                except Exception as e:
                    logger.error(f"❌ Error processing actuator command: {e}")
    except asyncio.CancelledError:
        logger.info("Actuator command subscriber cancelled.")
    finally:
        await pubsub.unsubscribe("actuator_commands")


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
            client_id=unique_client_id,
        )

        # Start in 'ingestion' mode
        await mqtt_service.start(mode="ingestion")
        logger.info("Async MQTT Service started in INGESTION mode.")

        # Start the actuator command bridge in the background
        bridge_task = asyncio.create_task(
            actuator_command_subscriber(redis_service, mqtt_service)
        )

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
