import os
from datetime import datetime, timezone
from typing import Any

from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync


class Settings:
    """Loads all environment variables for the application."""

    MQTT_BROKER: str = os.getenv("mqtt_broker_url", "localhost")
    MQTT_PORT: int = int(os.getenv("mqtt_broker_port", 1883))
    MQTT_USERNAME: str = os.getenv("mqtt_username")
    MQTT_PASSWORD: str = os.getenv("mqtt_password")

    INFLUXDB_URL: str = os.getenv("influxdb_url")
    INFLUXDB_TOKEN: str = os.getenv("influxdb_token")
    INFLUXDB_ORG: str = os.getenv("influxdb_org")
    INFLUXDB_BUCKET: str = os.getenv("influxdb_bucket")


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
        self._client: InfluxDBClientAsync | None = None
        self._write_api = None

    async def __aenter__(self):
        """Initializes the async client upon entering the context."""
        print("Initializing InfluxDB client...")
        self._client = InfluxDBClientAsync(
            url=self._url, token=self._token, org=self._org
        )
        self._write_api = self._client.get_write_api()
        print("InfluxDB client initialized.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the client connection upon exiting the context."""
        if self._client:
            await self._client.close()
            print("InfluxDB client closed.")

    async def ping(self) -> bool:
        """Checks the health of the InfluxDB connection."""
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except Exception as e:
            print(f"InfluxDB ping failed: {e}")
            return False

    async def save_sensor_data(self, device_id: str, sensor_data_list: list):
        """Asynchronously writes a batch of sensor data to InfluxDB."""
        if not self._write_api:
            print("Error: Write API is not initialized.")
            return
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
                    .tag("device_id", device_id)
                    .tag("sensor_id", str(sensor_id))
                    .tag("sensor_type", str(sensor_type))
                    .field("value", float(value))
                    .time(timestamp)
                )
                points.append(point)

            if points:
                await self._write_api.write(
                    bucket=self.bucket, org=self._org, record=points
                )
                print(f"Saved {len(points)} points to InfluxDB for device {device_id}")
        except Exception as e:
            print(f"Error saving to InfluxDB: {e}")

    async def query_data(self, query: str, params: dict[str, Any] | None = None):
        """
        Executes a Flux query against InfluxDB, using parameters to prevent injection.

        Args:
            query: The Flux query string, with placeholders for parameters.
            params: A dictionary of parameters to be safely substituted into the query.
        """
        if not self._client:
            raise ConnectionError("InfluxDB client is not available.")

        query_api = self._client.get_query_api()
        result = await query_api.query(query, org=self._org, params=params)
        return result
