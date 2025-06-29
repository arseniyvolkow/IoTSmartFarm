import paho.mqtt.client as mqtt
from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
# from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import os


class Settings:
    MQTT_BROKER: str = os.getenv("mqtt_broker_url")
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
        # Client is not created yet, just configured
        self._client = None
        self.write_api = None

    async def __aenter__(self):
        """Initializes the async client and write_api upon entering the context."""
        print("Initializing InfluxDB client...")
        self._client = InfluxDBClientAsync(url=self._url, token=self._token, org=self._org)
        self.write_api = self._client.get_write_api()
        print("InfluxDB client initialized.")
        return self # Return the instance to be used in the 'with' block

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the client connection upon exiting the context."""
        if self._client:
            await self._client.close()
            print("InfluxDB client closed.")

    # Your async save_sensor_data method from before goes here
    async def save_sensor_data(self, device_id: str, sensor_data_list: list):
        # (The implementation is the same as the previous answer)
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
                    .tag("sensor_id", sensor_id)
                    .tag("sensor_type", sensor_type)
                    .field("value", float(value))
                    .time(timestamp)
                )
                points.append(point)
            if points:
                await self.write_api.write(bucket=self.bucket, org=self._org, record=points)
                print(f"Saved {len(points)} points to InfluxDB for device {device_id}")
        except Exception as e:
            print(f"Error saving to InfluxDB: {e}")


# MQTT Service


class MQTTService:
    def __init__(self, broker, port, username, password, on_message_callback):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(username, password)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = on_message_callback

        self.broker = broker
        self.port = port

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT Broker. Result code: {rc}")
            client.subscribe("device/+/data")
        else:
            print(f"Failed to connect. Result code: {rc}")

    def start(self):
        try:
            self.mqtt_client.connect(self.broker, self.port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"Failed to start MQTT client: {e}")

    def stop(self):
        self.mqtt_client.loop_stop()
