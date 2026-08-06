import json
import logging
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisService:
    def __init__(self, host: str, port: int, db: int, password: str | None = None):
        self._host = host
        self._port = port
        self._db = db
        self.password = password
        self.client: redis.Redis | None = None

    async def connect(self):
        """Initialize Redis client and verify connection."""
        try:
            self.client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self.password,
                decode_responses=True,
                socket_timeout=5.0,
                health_check_interval=30,
            )
            await self.client.ping()
            logger.info(f"✅ Connected to Redis at {self._host}:{self._port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
            raise

    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            try:
                await self.client.close()
                logger.info("Redis connection closed.")
            except Exception as e:
                logger.error(f"Error disconnecting from Redis: {e}")
            finally:
                self.client = None

    def is_connected(self) -> bool:
        return self.client is not None

    async def get(self, sensor_id: str) -> str | None:
        """
        Получает сырое значение сенсора по его ID.
        Автоматически добавляет префикс 'sensor:', чтобы соответствовать Sensor Service.
        """
        if not self.client:
            logger.warning("Redis not connected, skipping get operation")
            return None

        key = f"sensor:{sensor_id}"
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.error(f"Error getting value for key '{key}': {e}")
            return None

    async def get_json(self, sensor_id: str) -> dict[str, Any] | float | str | None:
        """
        Получает и автоматически парсит JSON значение сенсора.
        Возвращает dict, если это JSON, или сырое значение/None.
        """
        raw_val = await self.get(sensor_id)
        if raw_val is None:
            return None

        try:
            return json.loads(raw_val)
        except json.JSONDecodeError:
            # Если там лежит не JSON, а просто число (например "25.5")
            logger.debug(f"Value for {sensor_id} is not JSON: {raw_val}")
            return raw_val
        except Exception as e:
            logger.error(f"Error parsing JSON for {sensor_id}: {e}")
            return None

    async def subscribe_to_channel(self, channel_name: str):
        """
        Subscribes to a Redis channel and returns the PubSub object.
        """
        if not self.client:
            logger.error("Redis client not initialized")
            return None

        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel_name)
        logger.info(f"📡 Subscribed to Redis channel: {channel_name}")
        return pubsub

    async def publish(self, channel_name: str, message: str):
        """
        Publishes a message to a Redis channel.
        """
        if not self.client:
            logger.error("Redis client not initialized")
            return None

        try:
            return await self.client.publish(channel_name, message)
        except Exception as e:
            logger.error(f"Error publishing to {channel_name}: {e}")
            return None

    async def ensure_consumer_group(self, stream_name: str, group_name: str):
        """
        Ensures a Redis Stream and consumer group exist. Creates them if they don't.
        """
        if not self.client:
            return False
        try:
            # Try to create the stream and group. mkstream=True automatically creates the stream if missing.
            await self.client.xgroup_create(
                stream_name, group_name, id="0", mkstream=True
            )
            logger.info(
                f"Created consumer group '{group_name}' for stream '{stream_name}'"
            )
            return True
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(
                    f"Consumer group '{group_name}' already exists for stream '{stream_name}'"
                )
                return True
            logger.error(f"Error creating consumer group: {e}")
            return False

    async def read_stream_group(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block: int = 2000,
    ):
        """
        Reads messages from a Redis stream using a consumer group.
        """
        if not self.client:
            return []
        try:
            # Read from the stream using the group. '>' means read new messages not yet delivered to the group.
            messages = await self.client.xreadgroup(
                group_name, consumer_name, {stream_name: ">"}, count=count, block=block
            )
            return messages
        except Exception as e:
            logger.error(f"Error reading from stream '{stream_name}': {e}")
            return []

    async def ack_message(self, stream_name: str, group_name: str, message_id: str):
        """
        Acknowledges a message in a Redis stream so it's removed from the pending entries list (PEL).
        """
        if not self.client:
            return False
        try:
            await self.client.xack(stream_name, group_name, message_id)
            return True
        except Exception as e:
            logger.error(
                f"Error acknowledging message '{message_id}' in stream '{stream_name}': {e}"
            )
            return False
