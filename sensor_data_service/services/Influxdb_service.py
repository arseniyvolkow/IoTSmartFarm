import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

logger = logging.getLogger(__name__)

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
        self._client: Optional[InfluxDBClientAsync] = None
        self.write_api = None
        self.query_api = None

    async def __aenter__(self):
        """Initializes the async client and APIs upon entering the context."""
        logger.info("Initializing InfluxDB client...")
        try:
            self._client = InfluxDBClientAsync(
                url=self._url, token=self._token, org=self._org
            )
            self.write_api = self._client.write_api()
            self.query_api = self._client.query_api()
            logger.info("✅ InfluxDB client initialized.")
            return self
        except Exception as e:
            logger.error(f"Failed to initialize InfluxDB client: {e}")
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the client connection upon exiting the context."""
        if self._client:
            await self._client.close()
            logger.info("InfluxDB client closed.")

    async def save_sensor_data(self, sensor_data_list: List[Dict[str, Any]]):
        """
        Save a batch of sensor data to InfluxDB.
        """
        if not self.write_api:
            logger.error("InfluxDB write_api is not initialized.")
            return

        try:
            points = []
            timestamp = datetime.now(timezone.utc)
            
            for sensor_data in sensor_data_list:
                sensor_id = sensor_data.get("sensor_id")
                sensor_type = sensor_data.get("sensor_type")
                value = sensor_data.get("value")
                
                # Валидация данных перед созданием точки
                if not all([sensor_id, sensor_type, value is not None]):
                    logger.warning(f"Skipping invalid sensor data: {sensor_data}")
                    continue
                
                try:
                    point = (
                        Point("sensor_data")
                        .tag("sensor_id", str(sensor_id))
                        .tag("sensor_type", str(sensor_type))
                        .field("value", float(value))
                        .time(timestamp)
                    )
                    points.append(point)
                except ValueError as ve:
                    logger.warning(f"Error converting value to float for sensor {sensor_id}: {ve}")
                    continue

            if points:
                await self.write_api.write(
                    bucket=self.bucket, org=self._org, record=points
                )
                logger.debug(f"Saved {len(points)} points to InfluxDB.")
                
        except Exception as e:
            logger.error(f"Error saving batch to InfluxDB: {e}")
            raise

    async def query_data_by_sensor_id(
        self, sensor_id: str, time_range: str
    ) -> List[Dict[str, Any]]:
        """
        Query time series data for a specific sensor ID.
        """
        if not self.query_api:
            logger.error("InfluxDB query_api is not initialized.")
            raise RuntimeError("InfluxDB client not connected")

        # Map frontend time ranges to InfluxDB flux duration syntax
        valid_times = {"1h": "-1h", "24h": "-24h", "7d": "-7d", "30d": "-30d"}
        
        if time_range not in valid_times:
            raise ValueError(
                f"Invalid time range '{time_range}'. Valid options: {', '.join(valid_times.keys())}"
            )

        # Flux Query: parameterized using f-string (safe here as we validate inputs)
        query = f"""
            from(bucket: "{self.bucket}")
                |> range(start: {valid_times[time_range]})
                |> filter(fn: (r) => r["_measurement"] == "sensor_data")
                |> filter(fn: (r) => r["_field"] == "value")
                |> filter(fn: (r) => r["sensor_id"] == "{sensor_id}")
                |> sort(columns: ["_time"])
        """
        
        try:
            result = await self.query_api.query(query, org=self._org)
            data_points = []
            
            for table in result:
                for record in table.records:
                    # Safely extract time
                    record_time = record.get_time()
                    time_str = record_time.isoformat() if record_time else None
                    
                    data_points.append({
                        "time": time_str,
                        "value": record.get_value(),
                        "sensor_id": record.values.get("sensor_id"),
                        "sensor_type": record.values.get("sensor_type"),
                    })
            
            return data_points
            
        except Exception as e:
            logger.error(f"Error querying InfluxDB for sensor_id '{sensor_id}': {e}")
            raise

    async def ping(self) -> bool:
        """Check if InfluxDB is accessible and ready."""
        if not self.query_api:
            return False
            
        try:
            # Simple query to check connectivity
            query = f'buckets() |> filter(fn: (r) => r.name == "{self.bucket}") |> limit(n: 1)'
            await self.query_api.query(query, org=self._org)
            return True
        except Exception as e:
            logger.error(f"InfluxDB ping failed: {e}")
            return False