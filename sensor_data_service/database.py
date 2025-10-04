from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from datetime import datetime, timezone
import os
import redis.asyncio as redis_client
import redis.exceptions
from typing import Optional, List, Dict, Any
import aiomqtt
import asyncio
import json
import logging

# Set up logger
logger = logging.getLogger(__name__)


class Settings:
    MQTT_BROKER: str = os.getenv("MQTT_BROKER_URL")
    MQTT_PORT: int = int(os.getenv("MQTT_BROKER_PORT", 1883))
    MQTT_USERNAME: str = os.getenv("MQTT_USERNAME")
    MQTT_PASSWORD: str = os.getenv("MQTT_PASSWORD")

    INFLUXDB_URL: str = os.getenv("influxdb_url")
    INFLUXDB_TOKEN: str = os.getenv("influxdb_token")
    INFLUXDB_ORG: str = os.getenv("influxdb_org")
    INFLUXDB_BUCKET: str = os.getenv("influxdb_bucket")

    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)


class RedisService:
    def __init__(self, host: str, port: int, db: int, password: Optional[str] = None):
        self._host = host
        self._port = port
        self._db = db
        self.password = password
        self.client: Optional[redis_client.Redis] = None
        self._connected = False

    async def connect(self):
        """Connect to Redis"""
        try:
            self.client = redis_client.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self.password,
                decode_responses=True,
            )
            await self.client.ping()
            self._connected = True
            print(f"Connected to Redis at {self._host}:{self._port}")
        except redis_client.ConnectionError as e:
            print(f"Redis connection error: {e}")
            self._connected = False
            self.client = None
        except redis_client.AuthenticationError as e:
            print(f"Redis authentication error: {e}")
            self._connected = False
            self.client = None
        except Exception as e:
            print(f"Unexpected Redis connection error: {e}")
            self._connected = False
            self.client = None

    async def disconnect(self):
        if self.client:
            try:
                await self.client.close()
                self._connected = False
            except Exception as e:
                print(f"Error disconnecting from redis: {e}")

    def is_connected(self):
        return self._connected and self.client is not None

    async def set_new_sensors_value(self, key, value):
        if not self.is_connected():
            raise Exception("Redis not connected")
        redis_key = f"sensor:{key}"
        try:
            await self.client.set(redis_key, value)
            return {"details": f"{redis_key} value added to redis"}
        except Exception as e:
            print(f"Error setting value for key '{key}': {e}")
            raise

    async def get_sensor_value(self, key):
        if not self.is_connected():
            raise Exception("Redis not connected")
        redis_key = f"sensor:{key}"
        try:
            sensor_value = await self.client.get(redis_key)
            return sensor_value
        except Exception as e:
            print(f"Error getting value for key '{key}': {e}")
            raise

    async def update_cache_from_batch(self, sensor_data_list: list):
        """Update Redis cache with a batch of sensor data using sensor_id as the key."""
        if not self.is_connected():
            print("Redis not connected, skipping cache update")
            return

        try:
            # Cache each sensor value individually using its unique sensor_id
            for sensor_data in sensor_data_list:
                sensor_key = sensor_data['sensor_id']
                await self.set_new_sensors_value(sensor_key, str(sensor_data["value"]))

            print(f"Successfully updated cache for {len(sensor_data_list)} sensors.")
        except Exception as e:
            print(f"Error updating Redis cache from batch: {e}")
            raise

class InfluxDBService:
    """
    Handles asynchronous communication with InfluxDB and manages its own lifecycle
    as an asynchronous context manager.
    """

    def __init__(self, url: str, token: str, org: str, bucket: str):
        self._url = url
        self._token = token
        self._org = org
        self.bucket = bucket
        self._client = None
        self.write_api = None
        self.query_api = None

    async def __aenter__(self):
        """Initializes the async client and APIs upon entering the context."""
        print("Initializing InfluxDB client...")
        self._client = InfluxDBClientAsync(
            url=self._url, token=self._token, org=self._org
        )
        self.write_api = self._client.write_api()
        self.query_api = self._client.query_api()
        print("InfluxDB client initialized.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the client connection upon exiting the context."""
        if self._client:
            await self._client.close()
            print("InfluxDB client closed.")

    # MODIFIED: Removed device_id from method signature and logic
    async def save_sensor_data(self, sensor_data_list: list):
        """Save sensor data to InfluxDB"""
        try:
            points = []
            timestamp = datetime.now(timezone.utc)
            for sensor_data in sensor_data_list:
                sensor_id = sensor_data.get("sensor_id")
                sensor_type = sensor_data.get("sensor_type")
                value = sensor_data.get("value")
                if not all([sensor_id, sensor_type, value is not None]):
                    print(f"Skipping invalid sensor data: {sensor_data}")
                    continue
                point = (
                    Point("sensor_data")
                    .tag("sensor_id", sensor_id)
                    .tag("sensor_type", sensor_type)
                    .field("value", float(value))
                    .time(timestamp)
                )
                points.append(point)
            if points:
                await self.write_api.write(
                    bucket=self.bucket, org=self._org, record=points
                )
                # MODIFIED: Updated print statement
                print(f"Saved {len(points)} points to InfluxDB.")
        except Exception as e:
            print(f"Error saving to InfluxDB: {e}")
            raise

    # MODIFIED: Renamed method and removed device_id from query
    async def query_sensor_data(
        self, sensor_type: str, time_range: str
    ) -> List[Dict[str, Any]]:
        """
        Query time series data for a specific sensor type

        Args:
            sensor_type: The sensor type to filter by
            time_range: Time range string (e.g., "1h", "24h", "7d", "30d")

        Returns:
            List of data points with timestamp, value, and metadata
        """
        valid_times = {"1h": "-1h", "24h": "-24h", "7d": "-7d", "30d": "-30d"}
        if time_range not in valid_times:
            raise ValueError(
                f"Invalid time range. Use: {', '.join(valid_times.keys())}"
            )

        # MODIFIED: Removed the device_id filter from the query
        query = f"""
            from(bucket: "{self.bucket}")
                |> range(start: {valid_times[time_range]})
                |> filter(fn: (r) => r["sensor_type"] == "{sensor_type}")
                |> filter(fn: (r) => r["_measurement"] == "sensor_data")
                |> filter(fn: (r) => r["_field"] == "value")
                |> sort(columns: ["_time"])
        """
        try:
            result = await self.query_api.query(query, org=self._org)
            data_points = []
            for table in result:
                for record in table.records:
                    data_points.append(
                        {
                            "time": (
                                record.get_time().isoformat()
                                if record.get_time()
                                else None
                            ),
                            "value": record.get_value(),
                            "sensor_id": record.values.get("sensor_id"),
                            "sensor_type": record.values.get("sensor_type"),
                        }
                    )
            return data_points
        except Exception as e:
            print(f"Error querying InfluxDB: {e}")
            raise

    # MODIFIED: Renamed method and removed device_id from query
    async def query_all_sensors(self, time_range: str) -> List[Dict[str, Any]]:
        """
        Query all sensor data

        Args:
            time_range: Time range string (e.g., "1h", "24h", "7d", "30d")

        Returns:
            List of data points for all sensors
        """
        valid_times = {"1h": "-1h", "24h": "-24h", "7d": "-7d", "30d": "-30d"}
        if time_range not in valid_times:
            raise ValueError(
                f"Invalid time range. Use: {', '.join(valid_times.keys())}"
            )

        # MODIFIED: Removed the device_id filter from the query
        query = f"""
            from(bucket: "{self.bucket}")
                |> range(start: {valid_times[time_range]})
                |> filter(fn: (r) => r["_measurement"] == "sensor_data")
                |> filter(fn: (r) => r["_field"] == "value")
                |> sort(columns: ["_time"])
        """
        try:
            result = await self.query_api.query(query, org=self._org)
            data_points = []
            for table in result:
                for record in table.records:
                    data_points.append(
                        {
                            "time": (
                                record.get_time().isoformat()
                                if record.get_time()
                                else None
                            ),
                            "value": record.get_value(),
                            "sensor_id": record.values.get("sensor_id"),
                            "sensor_type": record.values.get("sensor_type"),
                        }
                    )
            return data_points
        except Exception as e:
            print(f"Error querying InfluxDB: {e}")
            raise

    # MODIFIED: Removed device_id from query
    async def get_latest_sensor_values(self) -> List[Dict[str, Any]]:
        """
        Get the latest values for all sensors

        Returns:
            List of latest sensor values
        """
        # MODIFIED: Removed the device_id filter from the query
        query = f"""
            from(bucket: "{self.bucket}")
                |> range(start: -24h)
                |> filter(fn: (r) => r["_measurement"] == "sensor_data")
                |> filter(fn: (r) => r["_field"] == "value")
                |> group(columns: ["sensor_type"])
                |> last()
        """
        try:
            result = await self.query_api.query(query, org=self._org)
            latest_values = []
            for table in result:
                for record in table.records:
                    latest_values.append(
                        {
                            "time": (
                                record.get_time().isoformat()
                                if record.get_time()
                                else None
                            ),
                            "value": record.get_value(),
                            "sensor_id": record.values.get("sensor_id"),
                            "sensor_type": record.values.get("sensor_type"),
                        }
                    )
            return latest_values
        except Exception as e:
            print(f"Error querying latest values from InfluxDB: {e}")
            raise

    async def ping(self) -> bool:
        """Check if InfluxDB is accessible"""
        try:
            query = f'buckets() |> filter(fn: (r) => r.name == "{self.bucket}") |> limit(n: 1)'
            await self.query_api.query(query, org=self._org)
            return True
        except Exception as e:
            print(f"InfluxDB ping failed: {e}")
            return False


class AsyncMQTTService:
    def __init__(
        self,
        broker: str,
        port: int,
        username: str,
        password: str,
        influx_service,  # InfluxDBService
        redis_service,  # RedisService
        client_id: str = None,
        keepalive: int = 60,
        reconnect_interval: int = 5,
    ):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.keepalive = keepalive
        self.reconnect_interval = reconnect_interval
        self.influx_service = influx_service
        self.redis_service = redis_service

        self.client: Optional[aiomqtt.Client] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._connected = False

        self._publish_queue = asyncio.Queue()
        self._publish_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the MQTT service with persistent connection"""
        if self._running:
            print("MQTT service is already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_client())
        self._publish_task = asyncio.create_task(self._process_publish_queue())
        print("Async MQTT Service started.")

    async def stop(self):
        """Stop the MQTT service"""
        self._running = False
        if self._task:
            self._task.cancel()
        if self._publish_task:
            self._publish_task.cancel()

        tasks_to_wait = [t for t in [self._task, self._publish_task] if t]
        if tasks_to_wait:
            try:
                await asyncio.gather(*tasks_to_wait, return_exceptions=True)
            except Exception:
                pass

        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None

        self._connected = False
        print("Async MQTT Service stopped.")

    async def _run_client(self):
        """
        MODIFIED: Main MQTT client loop using the 'async with' context manager
        and the correct 'identifier' keyword argument.
        """
        while self._running:
            try:
                # The 'async with' block handles connect() and disconnect() automatically
                async with aiomqtt.Client(
                    hostname=self.broker,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    keepalive=self.keepalive,
                    # MODIFIED: Changed 'client_id' to 'identifier'
                    identifier=self.client_id,
                ) as client:
                    # Assign the active client to the class instance so other methods can use it
                    self.client = client
                    self._connected = True
                    print(f"Connected to MQTT broker at {self.broker}:{self.port}")

                    # Subscribe to topics
                    await self.client.subscribe("device/+/data")
                    print("Subscribed to device/+/data")

                    # Listen for messages
                    async for message in self.client.messages:
                        if not self._running:
                            break
                        await self._handle_message(message)

            except aiomqtt.MqttError as e:
                self._connected = False
                self.client = None
                print(f"MQTT connection error: {e}")
                if self._running:
                    print(
                        f"Attempting to reconnect in {self.reconnect_interval} seconds..."
                    )
                    await asyncio.sleep(self.reconnect_interval)
            except Exception as e:
                self._connected = False
                self.client = None
                print(f"Unexpected MQTT error: {e}")
                if self._running:
                    await asyncio.sleep(self.reconnect_interval)
            finally:
                # Clean up status on disconnect
                self._connected = False
                self.client = None

    async def _process_publish_queue(self):
        """Process queued publish requests"""
        while self._running:
            try:
                try:
                    publish_request = await asyncio.wait_for(
                        self._publish_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                topic, payload, qos = publish_request

                while self._running and not self._connected:
                    await asyncio.sleep(0.1)

                if not self._running:
                    break

                await self._publish_direct(topic, payload, qos)

            except Exception as e:
                print(f"Error in publish queue processor: {e}")

    async def _publish_direct(self, topic: str, payload: dict, qos: int):
        """Direct publish using the persistent connection"""
        try:
            if not self._connected or not self.client:
                raise Exception("MQTT client not connected")

            payload_str = (
                json.dumps(payload) if isinstance(payload, dict) else str(payload)
            )
            await self.client.publish(
                topic, payload=payload_str.encode("utf-8"), qos=qos
            )
            print(f"Published to topic '{topic}': {payload_str}")

        except Exception as e:
            print(f"Failed to publish message directly: {e}")
            raise

    async def publish_mqtt_message(self, topic: str, payload, qos: int = 1):
        """Queue a message for publishing."""
        try:
            if isinstance(payload, dict):
                formatted_payload = payload
            elif isinstance(payload, str):
                try:
                    formatted_payload = json.loads(payload)
                except json.JSONDecodeError:
                    formatted_payload = {"message": payload}
            else:
                formatted_payload = {"value": str(payload)}

            await self._publish_queue.put((topic, formatted_payload, qos))
        except Exception as e:
            print(f"Failed to queue message for publishing: {e}")
            raise
        return {"details": "OK"}

    async def publish_mqtt_message_sync(self, topic: str, payload: dict, qos: int = 1):
        """Synchronously publish a message using the persistent connection."""
        if not self._connected:
            raise Exception("MQTT client not connected")
        await self._publish_direct(topic, payload, qos)

    async def _handle_message(self, message: aiomqtt.Message):
        """Handle incoming MQTT messages"""
        try:
            # We still parse the device_id from the topic, though it's not used for caching
            topic_parts = str(message.topic).split("/")
            if len(topic_parts) < 2:
                print(f"Invalid topic format: {message.topic}")
                return
            unique_device_id = topic_parts[1]

            # ... payload parsing logic ...
            try:
                payload = json.loads(message.payload.decode())
            except json.JSONDecodeError:
                print("Error: Payload is not valid JSON")
                return

            sensor_data = payload.get("sensors", {})
            if not sensor_data:
                print(f"Invalid payload for device {unique_device_id}: Missing 'sensors'")
                return
            
            sensor_data_list = self._convert_sensor_data(sensor_data)

            # MODIFIED: The call to _update_redis_cache no longer passes device_id
            await asyncio.gather(
                self._save_to_influxdb(sensor_data_list),
                self._update_redis_cache(sensor_data_list),
                return_exceptions=True
            )

        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    def _convert_sensor_data(self, sensor_data) -> list:
        """Convert sensor data dict to list format expected by InfluxDB"""
        sensor_data_list = []
        if isinstance(sensor_data, dict):
            for sensor_key, sensor_value in sensor_data.items():
                if isinstance(sensor_value, dict) and "value" in sensor_value:
                    sensor_data_list.append(
                        {
                            "sensor_id": sensor_key,
                            "sensor_type": sensor_value.get("sensor_type", sensor_key),
                            "value": sensor_value["value"],
                        }
                    )
                else:
                    sensor_data_list.append(
                        {
                            "sensor_id": sensor_key,
                            "sensor_type": sensor_key,
                            "value": sensor_value,
                        }
                    )
        elif isinstance(sensor_data, list):
            sensor_data_list = sensor_data
        return sensor_data_list

    # MODIFIED: Removed device_id from signature and call
    async def _save_to_influxdb(self, sensor_data_list: list):
        """Save sensor data to InfluxDB"""
        try:
            await self.influx_service.save_sensor_data(sensor_data_list)
            print(f"Successfully saved data to InfluxDB.")
        except Exception as e:
            print(f"Error saving sensor data to InfluxDB: {e}")

    async def _update_redis_cache(self, sensor_data_list: list):
        """
        Update Redis cache by calling the generic batch update method.
        """
        try:
            # This ensures caching logic is identical for both MQTT and direct API calls
            await self.redis_service.update_cache_from_batch(sensor_data_list)
        except Exception as e:
            # The specific error will be printed by the method in RedisService
            print(f"Error updating Redis cache from MQTT message: {e}")

    def is_connected(self) -> bool:
        return self._running and self._connected

    def is_running(self) -> bool:
        return self._running

    async def get_connection_status(self) -> dict:
        return {
            "running": self._running,
            "connected": self._connected,
            "broker": f"{self.broker}:{self.port}",
            "queue_size": self._publish_queue.qsize() if self._publish_queue else 0,
        }
