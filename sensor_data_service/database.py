import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
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
    def __init__(self, url, token, org, bucket):
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.bucket = bucket
        self.org = org

    def save_sensor_data(self, device_id, sensor_data):
        try:
            for sensor_type, value in sensor_data.items():
                point = (
                    Point("sensor_data")
                    .tag("device_id", device_id)
                    .tag("sensor_type", sensor_type)  # Add sensor_type as tag
                    .field("value", value)            # Use consistent field name
                    .time(datetime.now(timezone.utc))
                )
                self.write_api.write(bucket=self.bucket,
                                   org=self.org, record=point)
                print(f"Saved to InfluxDB: {sensor_type} = {value}")
        except Exception as e:
            print(f"Error saving to InfluxDB: {e}")

    def close(self):
        self.client.close()

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
