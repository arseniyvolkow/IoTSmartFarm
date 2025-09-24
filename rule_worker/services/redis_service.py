# redis_service.py
from typing import Optional
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)


class RedisService:
    def __init__(self, host: str, port: int, db: int, password: Optional[str] = None):
        self._host = host
        self._port = port
        self._db = db
        self.password = password
        self.client: Optional[redis.Redis] = None
        self._connected = False

    async def connect(self):
        """Connect to Redis"""
        try:
            logger.info(f"Connecting to Redis: {self._host}:{self._port}")
            
            # Connect using redis.asyncio
            self.client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            result = await self.client.ping()
            if result:
                self._connected = True
                logger.info(f"Connected to Redis at {self._host}:{self._port}")
            else:
                raise Exception("Redis ping failed")
                
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            if self.client:
                try:
                    await self.client.close()
                except:
                    pass
            self.client = None
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            try:
                await self.client.close()
                self._connected = False
                logger.info("Disconnected from Redis")
            except Exception as e:
                logger.error(f"Error disconnecting from redis: {e}")

    def is_connected(self):
        """Check if Redis is connected"""
        return self._connected and self.client is not None

    async def set_new_sensors_value(self, key: str, value: str):
        """Set sensor value in Redis"""
        if not self.is_connected():
            raise Exception("Redis not connected")
        redis_key = f"sensor:{key}"
        try:
            await self.client.set(redis_key, value)
            return {"details": f"{redis_key} value added to redis"}
        except Exception as e:
            logger.error(f"Error setting value for key '{key}': {e}")
            raise

    async def get_sensor_value(self, key: str):
        """Get sensor value from Redis"""
        if not self.is_connected():
            raise Exception("Redis not connected")
        redis_key = f"sensor:{key}"
        try:
            sensor_value = await self.client.get(redis_key)
            return sensor_value
        except Exception as e:
            logger.error(f"Error getting value for key '{key}': {e}")
            raise

    # Context manager support
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# Test function
async def test_connection():
    import os
    service = RedisService(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=int(os.getenv('REDIS_DB', 0)),
        password=os.getenv('REDIS_PASSWORD')
    )
    
    try:
        await service.connect()
        print("✅ Redis connected!")
        
        await service.set_new_sensors_value("test", "hello")
        value = await service.get_sensor_value("test")
        print(f"✅ Test value: {value}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_connection())