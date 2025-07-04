import json
from .database import InfluxDBService


class SensorDataHandler:
    """Handles the business logic for processing incoming sensor data messages."""

    def __init__(self, influxdb_service: InfluxDBService):
        self.influxdb_service = influxdb_service

    async def handle_message(self, topic: str, payload: bytes):
        """Parses an MQTT message and saves the data to InfluxDB."""
        print(f"Received message on topic: {topic}")
        try:
            topic_parts = topic.split("/")
            # Expecting topic format "device/+/data"
            if (
                len(topic_parts) != 3
                or topic_parts[0] != "device"
                or topic_parts[2] != "data"
            ):
                print(f"Ignoring message on unhandled topic format: {topic}")
                return

            unique_device_id = topic_parts[1]
            payload_data = json.loads(payload.decode())

            # The payload should be a list of sensor readings
            sensor_data_list = payload_data.get("sensors")

            if not isinstance(sensor_data_list, list):
                print(
                    f"Invalid payload for device {unique_device_id}: 'sensors' field must be a list."
                )
                return

            await self.influxdb_service.save_sensor_data(
                unique_device_id, sensor_data_list
            )

        except json.JSONDecodeError:
            print(f"Error: Payload on topic {topic} is not valid JSON.")
        except Exception as e:
            print(f"Error processing message from topic {topic}: {e}")
