from fastapi import FastAPI, HTTPException
from influxdb_client import InfluxDBClient
from .database import Settings, MQTTService, InfluxDBService
import json


settings = Settings()

# Lifespan function

influxdb_service = InfluxDBService(
    url=settings.INFLUXDB_URL,
    token=settings.INFLUXDB_TOKEN,
    org=settings.INFLUXDB_ORG,
    bucket=settings.INFLUXDB_BUCKET
)


def handle_mqtt_message(client, userdata, message):
    try:
        topic_parts = message.topic.split('/')
        unique_device_id = topic_parts[1]
        payload = json.loads(message.payload.decode())
        sensor_data = payload.get("sensors", {})

        if not sensor_data:
            print("Invalid payload: Missing 'sensors'")
            return

        try:
            influxdb_service.save_sensor_data(unique_device_id, sensor_data)
        except Exception as e:
            print(f"Error saving sensor data to InfluxDB: {e}")
    except json.JSONDecodeError:
        print("Error: Payload is not valid JSON")
    except Exception as e:
        print(f"Error processing message: {e}")


mqtt_service = MQTTService(
    broker=settings.MQTT_BROKER,
    port=settings.MQTT_PORT,
    username=settings.MQTT_USERNAME,
    password=settings.MQTT_PASSWORD,
    on_message_callback=handle_mqtt_message
)

async def lifespan(app: FastAPI):
    try:
        mqtt_service.start()
        print("MQTT Service started.")
        yield  # App will run while this generator yields
    except Exception as e:
        print(f"Error during startup: {e}")
        raise
    finally:
        mqtt_service.stop()
        influxdb_service.close()
        print("MQTT Service stopped and InfluxDB Service closed.")


# FastAPI application
app = FastAPI(lifespan=lifespan, root_path='/api/sensor-data')
# Instantiate services


@app.get("/health")
async def health_check():
    mqtt_status = "connected" if mqtt_service.mqtt_client.is_connected() else "disconnected"
    return {
        "status": "running",
        "mqtt_status": mqtt_status,
        "influxdb_status": "connected" if influxdb_service.client.ping() else "disconnected",
    }
 

@app.post("/simulate-sensor-data")
async def simulate_sensor_data(device_id: str, sensor_key: str, value: float):
    sensor_data = {sensor_key: value}
    influxdb_service.save_sensor_data(device_id, sensor_data)
    return {"status": "simulated data saved"}


@app.get('/device_data/{device_id}/{sensor_type}/{time}')
async def get_timeseries_data_for_device(device_id, sensor_type, time):
    try:
        # Validate time parameter
        valid_times = {'1h': '-1h', '24h': '-24h', '7d': '-7d', '30d': '-30d'}
        if time not in valid_times:
            raise HTTPException(status_code=400, detail="Invalid time parameter. Use: 1h, 24h, 7d, or 30d")
        
        # Construct Flux query
        query = f'''
            from(bucket: "{settings.INFLUXDB_BUCKET}")
                |> range(start: {valid_times[time]})
                |> filter(fn: (r) => r["device_id"] == "{device_id}")
                |> filter(fn: (r) => r["sensor_type"] == "{sensor_type}")
                |> sort(columns: ["_time"])
        '''
        # Query InfluxDB
        try:
            result = influxdb_service.client.query_api().query(query, org=settings.influxdb_org)
            # Process the result if needed
            return {"status": "success", "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error querying data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying data: {str(e)}")