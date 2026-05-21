import logging
import orjson
from typing import Optional, List, Dict, Any
import redis.asyncio as redis_client

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self, host: str, port: int, db: int, password: Optional[str] = None):
        self._host = host
        self._port = port
        self._db = db
        self.password = password
        self.client: Optional[redis_client.Redis] = None

    async def connect(self):
        """Initialize Redis client and verify connection."""
        try:
            self.client = redis_client.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self.password,
                decode_responses=True,
                socket_timeout=5.0
            )
            await self.client.ping()
            logger.info(f"✅ Connected to Redis at {self._host}:{self._port}")
        except redis_client.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            self.client = None
            raise
        except redis_client.AuthenticationError as e:
            logger.error(f"Redis authentication error: {e}")
            self.client = None
            raise
        except Exception as e:
            logger.exception(f"Unexpected Redis connection error: {e}")
            self.client = None
            raise

    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            try:
                await self.client.close()
                logger.info("Redis connection closed.")
            except Exception as e:
                logger.error(f"Error disconnecting from redis: {e}")
            finally:
                self.client = None

    def is_connected(self) -> bool:
        return self.client is not None

    async def set_new_sensors_value(self, key: str, value: Any):
        """Set a single sensor value."""
        if not self.client:
            logger.warning("Redis not connected, skipping set operation")
            return

        redis_key = f"sensor:{key}"
        try:
            await self.client.set(redis_key, str(value))
            logger.debug(f"Set {redis_key} = {value}")
        except Exception as e:
            logger.error(f"Error setting value for key '{key}': {e}")
            raise

    async def get_sensor_value(self, key: str) -> Optional[str]:
        """Get a single sensor value."""
        if not self.client:
            logger.warning("Redis not connected, skipping get operation")
            return None

        redis_key = f"sensor:{key}"
        try:
            return await self.client.get(redis_key)
        except Exception as e:
            logger.error(f"Error getting value for key '{key}': {e}")
            raise

    async def get_cached_history(self, sensor_id: str, time_range: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached InfluxDB history to save CPU and DB load."""
        if not self.client:
            return None
            
        redis_key = f"history:{sensor_id}:{time_range}"
        try:
            cached_data = await self.client.get(redis_key)
            if cached_data:
                return orjson.loads(cached_data)
            return None
        except Exception as e:
            logger.error(f"Error reading cache for history {redis_key}: {e}")
            return None

    async def set_cached_history(self, sensor_id: str, time_range: str, data: List[Dict[str, Any]], ttl: int = 15):
        """Cache InfluxDB history for a short duration (default 15s) using fast orjson."""
        if not self.client:
            return
            
        redis_key = f"history:{sensor_id}:{time_range}"
        try:
            # decode() because orjson.dumps returns bytes, but our redis_client has decode_responses=True
            json_data = orjson.dumps(data).decode('utf-8')
            await self.client.setex(redis_key, ttl, json_data)
        except Exception as e:
            logger.error(f"Error caching history for {redis_key}: {e}")

    async def update_cache_from_batch(self, sensor_data_list: List[Dict[str, Any]]):
        """
        Efficiently update Redis cache with a batch of sensor data using a pipeline.
        sensor_data_list expected format: [{'sensor_id': '...', 'value': ...}, ...]
        Also publishes an event to 'sensor_updates' channel for real-time rule evaluation.
        """
        if not self.client:
            logger.warning("Redis not connected, skipping batch update")
            return

        try:
            # Используем Pipeline для отправки всех команд за один раз
            async with self.client.pipeline() as pipe:
                for sensor_data in sensor_data_list:
                    sensor_id = sensor_data['sensor_id']
                    sensor_key = f"sensor:{sensor_id}"
                    value = str(sensor_data["value"])
                    
                    # Обновляем значение
                    pipe.set(sensor_key, value)
                    
                    # Публикуем событие об обновлении в Redis Stream
                    # Payload: {"sensor_id": "...", "value": ...}
                    # Using orjson for speed, decoding to string for the pipeline
                    event_payload = orjson.dumps({
                        "sensor_id": sensor_id,
                        "value": sensor_data["value"]
                    }).decode('utf-8')
                    
                    # Изменили publish на xadd (Redis Streams)
                    pipe.xadd("sensor_updates", {"data": event_payload})
                
                # Выполняем все команды скопом
                await pipe.execute()
                
            logger.debug(f"Successfully cached and published {len(sensor_data_list)} sensor readings via pipeline.")
            
        except Exception as e:
            logger.error(f"Error updating Redis cache from batch: {e}")
            raise