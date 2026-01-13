import json
import logging
from typing import Optional, Dict, Any, Union
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self, host: str, port: int, db: int, password: Optional[str] = None):
        self._host = host
        self._port = port
        self._db = db
        self.password = password
        self.client: Optional[redis.Redis] = None

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
                health_check_interval=30
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

    async def get(self, sensor_id: str) -> Optional[str]:
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

    async def get_json(self, sensor_id: str) -> Optional[Union[Dict[str, Any], float, str]]:
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