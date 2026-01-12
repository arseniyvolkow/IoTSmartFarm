import os
from typing import Optional
import logging

# Set up logger
logger = logging.getLogger(__name__)


class Settings:
    MQTT_BROKER: str = os.getenv("MQTT_BROKER_URL")
    MQTT_PORT: int = int(os.getenv("MQTT_BROKER_PORT", 1883))
    MQTT_USERNAME: str = os.getenv("MQTT_USERNAME")
    MQTT_PASSWORD: str = os.getenv("MQTT_PASSWORD")

    INFLUXDB_URL: str = os.getenv("INFLUXDB_URL")
    INFLUXDB_TOKEN: str = os.getenv("INFLUXDB_TOKEN")
    INFLUXDB_ORG: str = os.getenv("INFLUXDB_ORG")
    INFLUXDB_BUCKET: str = os.getenv("INFLUXDB_BUCKET")

    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)


