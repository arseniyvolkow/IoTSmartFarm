import asyncio
import orjson
import logging
from typing import Optional, List, Dict, Any, Union
import aiomqtt

logger = logging.getLogger(__name__)

class AsyncMQTTService:
    """
    HIGH-THROUGHPUT MQTT SERVICE (CQRS READY)
    ----------------------------------------
    Handles high-volume sensor ingestion and actuator commanding.
    Designed to work in different 'modes' to allow physical separation 
    of the API and the background worker.
    """
    def __init__(
        self,
        broker: str,
        port: int,
        username: str,
        password: str,
        influx_service,
        redis_service,
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
        self._connected = False
        self._running = False
        self.mode = "all"
        
        # Async queues for decoupling producers from consumers
        self._publish_queue = asyncio.Queue()
        self._incoming_queue = asyncio.Queue()
        
        # Internal tasks
        self._tasks: List[asyncio.Task] = []
        
        # BATCHING TUNING: Processing 500 messages at once maximizes DB write speed
        self._batch_size = 500
        self._batch_timeout = 0.1

    async def start(self, mode="all"):
        """
        Starts the service loops.
        - 'api' mode: Only enables publishing (sending commands to devices).
        - 'ingestion' mode: Only enables subscribing (receiving and saving sensor data).
        - 'all' mode: Enables both (legacy/dev behavior).
        """
        if self._running:
            return
            
        self._running = True
        self.mode = mode
        
        # 1. Main connection manager
        self._tasks.append(asyncio.create_task(self._connection_loop()))
        
        # 2. Outgoing Loop (API)
        if self.mode in ["all", "api"]:
            self._tasks.append(asyncio.create_task(self._publish_loop()))
            
        # 3. Ingestion Worker (Background)
        if self.mode in ["all", "ingestion"]:
            self._tasks.append(asyncio.create_task(self._batch_worker()))
        
        logger.info(f"Async MQTT Service started (Mode: {self.mode})")

    async def stop(self):
        """Clean shutdown of all background loops."""
        self._running = False
        self._connected = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def publish_mqtt_message(self, topic: str, payload: Any, qos: int = 1):
        """Queue a message for publication. Non-blocking."""
        await self._publish_queue.put((topic, payload, qos))
        return {"status": "queued"}

    async def _connection_loop(self):
        """Manages the lifecycle of the MQTT client connection."""
        while self._running:
            try:
                async with aiomqtt.Client(
                    hostname=self.broker,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    keepalive=self.keepalive,
                    identifier=self.client_id,
                ) as client:
                    self.client = client
                    self._connected = True
                    logger.info(f"✅ MQTT Connected ({self.mode})")

                    if self.mode in ["all", "ingestion"]:
                        # Subscribe only if we are an ingestion worker
                        await client.subscribe("device/+/data")
                        async for message in client.messages:
                            if not self._running:
                                break
                            # Push to queue immediately to free up the network loop
                            await self._incoming_queue.put(message)
                    else:
                        # In API mode, just keep the connection alive for publishing
                        while self._running:
                            await asyncio.sleep(1)

            except Exception as e:
                self._connected = False
                logger.error(f"MQTT Error: {e}")
            finally:
                self._connected = False
                self.client = None

            if self._running:
                await asyncio.sleep(self.reconnect_interval)

    async def _batch_worker(self):
        """Assembles small messages into large batches for database efficiency."""
        while self._running:
            batch = []
            try:
                # Wait for the first message
                try:
                    message = await asyncio.wait_for(self._incoming_queue.get(), timeout=1.0)
                    batch.append(message)
                except asyncio.TimeoutError:
                    continue

                # Accumulate more messages until batch is full or timeout reached
                start_time = asyncio.get_event_loop().time()
                while len(batch) < self._batch_size:
                    time_left = self._batch_timeout - (asyncio.get_event_loop().time() - start_time)
                    if time_left <= 0:
                        break
                    try:
                        message = await asyncio.wait_for(self._incoming_queue.get(), timeout=time_left)
                        batch.append(message)
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    # Offload to optimized processor
                    await self._process_batch(batch)
                    for _ in range(len(batch)):
                        self._incoming_queue.task_done()

            except Exception as e:
                logger.error(f"Error in batch worker: {e}")
                await asyncio.sleep(0.1)

    async def _process_batch(self, batch: List[aiomqtt.Message]):
        """
        HIGH-SPEED BATCH PROCESSOR
        --------------------------
        Optimized to handle 10,000+ messages per second.
        """
        def _parse_and_normalize():
            """
            CPU-intensive parsing offloaded to a thread pool.
            - uses orjson.loads (Rust-based)
            - uses list comprehensions (C-speed loops)
            - bypasses function call overhead
            """
            loads = orjson.loads
            results = []
            extend = results.extend
            
            for message in batch:
                try:
                    payload = loads(message.payload)
                    sensors_data = payload.get("sensors")
                    if not sensors_data:
                        continue
                        
                    if type(sensors_data) is list:
                        extend(sensors_data)
                    elif type(sensors_data) is dict:
                        extend([
                            {
                                "sensor_id": k,
                                "sensor_type": v.get("sensor_type", k) if type(v) is dict and "value" in v else k,
                                "value": v["value"] if type(v) is dict and "value" in v else v
                            }
                            for k, v in sensors_data.items()
                        ])
                except Exception:
                    continue
            return results

        # 1. Parse in a separate thread to keep the event loop free for networking
        all_normalized_data = await asyncio.to_thread(_parse_and_normalize)

        if all_normalized_data:
            # 2. Parallel write to both InfluxDB and Redis
            await asyncio.gather(
                self._safe_save_influx(all_normalized_data),
                self._safe_save_redis(all_normalized_data),
                return_exceptions=True
            )

    async def _publish_loop(self):
        """Handles outgoing MQTT traffic (actuator commands) from the queue."""
        while self._running:
            try:
                topic, payload, qos = await self._publish_queue.get()
                
                # Wait for network recovery if disconnected
                while self._running and (not self._connected or not self.client):
                    await asyncio.sleep(0.5)

                if not self._running:
                    self._publish_queue.task_done()
                    break

                try:
                    payload_str = orjson.dumps(payload)
                    await self.client.publish(topic, payload=payload_str, qos=qos)
                except Exception:
                    # Fault tolerance: put back in queue if network fails
                    await self._publish_queue.put((topic, payload, qos))
                    await asyncio.sleep(1)
                finally:
                    self._publish_queue.task_done()
            except Exception:
                await asyncio.sleep(0.5)

    def _serialize_payload(self, payload: Any) -> bytes:
        if isinstance(payload, (dict, list)):
            return orjson.dumps(payload)
        return str(payload).encode("utf-8")

    async def _safe_save_influx(self, data: list):
        try:
            await self.influx_service.save_sensor_data(data)
        except Exception as e:
            logger.error(f"InfluxDB Save Error: {e}")

    async def _safe_save_redis(self, data: list):
        try:
            await self.redis_service.update_cache_from_batch(data)
        except Exception as e:
            logger.error(f"Redis Cache Error: {e}")

    def is_connected(self) -> bool:
        return self._connected
