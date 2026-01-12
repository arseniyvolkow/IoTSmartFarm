import asyncio
import json
import logging
from typing import Optional, List, Dict, Any, Union
import aiomqtt

logger = logging.getLogger(__name__)

class AsyncMQTTService:
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
        
        # Храним задачи в списке, чтобы их было удобно отменять скопом
        self._tasks: List[asyncio.Task] = []
        self._publish_queue = asyncio.Queue()

    async def start(self):
        """Запуск сервиса: инициализация подключения и воркера отправки."""
        if self._running:
            logger.warning("MQTT service is already running")
            return
            
        self._running = True
        # Запускаем два основных цикла: чтение (подключение) и запись (публикация)
        self._tasks.append(asyncio.create_task(self._connection_loop()))
        self._tasks.append(asyncio.create_task(self._publish_loop()))
        
        logger.info(f"Async MQTT Service started (Broker: {self.broker}:{self.port})")

    async def stop(self):
        """Остановка сервиса и очистка ресурсов."""
        logger.info("Stopping MQTT Service...")
        self._running = False
        self._connected = False
        
        # Отменяем все фоновые задачи
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            # Ждем завершения отмены задач
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        logger.info("Async MQTT Service stopped.")

    async def publish_mqtt_message(self, topic: str, payload: Any, qos: int = 1):
        """
        Публичный метод для отправки сообщений.
        Просто кладет задачу в очередь, не блокируя поток.
        """
        await self._publish_queue.put((topic, payload, qos))
        return {"status": "queued"}

    # --- Внутренние методы (Internal Loops) ---

    async def _connection_loop(self):
        """Главный цикл управления подключением и подпиской."""
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
                    logger.info("✅ Connected to MQTT Broker")

                    # Подписываемся на топики
                    await client.subscribe("device/+/data")
                    logger.info("Subscribed to: device/+/data")

                    # Обработка входящих сообщений
                    async for message in client.messages:
                        if not self._running:
                            break
                        # Запускаем обработку сообщения в фоне, чтобы не тормозить цикл чтения
                        asyncio.create_task(self._handle_message(message))

            except aiomqtt.MqttError as e:
                self._connected = False
                logger.error(f"MQTT Connection error: {e}")
            except Exception as e:
                self._connected = False
                logger.exception(f"Unexpected error in MQTT loop: {e}")
            finally:
                self._connected = False
                self.client = None

            # Если мы вылетели из контекстного менеджера (разрыв), ждем перед реконнектом
            if self._running:
                logger.info(f"Reconnecting in {self.reconnect_interval}s...")
                await asyncio.sleep(self.reconnect_interval)

    async def _publish_loop(self):
        """Воркер, который разгребает очередь на отправку."""
        while self._running:
            try:
                # Ждем задачу из очереди
                topic, payload, qos = await self._publish_queue.get()
                
                # Если нет соединения, ждем (или можно дропать сообщения, зависит от требований)
                while self._running and not self._connected:
                    await asyncio.sleep(0.5)

                if not self._running:
                    break

                if self.client:
                    payload_str = self._serialize_payload(payload)
                    await self.client.publish(
                        topic, 
                        payload=payload_str.encode("utf-8"), 
                        qos=qos
                    )
                    logger.debug(f"Published to {topic}: {payload_str}")
                
                self._publish_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in publish loop: {e}")

    # --- Обработка данных (Data Processing) ---

    async def _handle_message(self, message: aiomqtt.Message):
        """Обработка одного сообщения."""
        try:
            topic = str(message.topic)
            payload_str = message.payload.decode()
            
            # 1. Валидация JSON
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON on {topic}: {payload_str[:50]}...")
                return

            # 2. Извлечение данных
            sensors_data = payload.get("sensors")
            if not sensors_data:
                logger.debug(f"Payload missing 'sensors' key on {topic}")
                return

            # 3. Нормализация данных
            normalized_data = self._normalize_sensor_data(sensors_data)
            
            # 4. Сохранение (Параллельно в Influx и Redis)
            # return_exceptions=True не даст одной ошибке (например, Influx) поломать вторую (Redis)
            await asyncio.gather(
                self._safe_save_influx(normalized_data),
                self._safe_save_redis(normalized_data),
                return_exceptions=True
            )

        except Exception as e:
            logger.error(f"Critical error handling message from {topic}: {e}")

    def _normalize_sensor_data(self, sensor_data: Union[Dict, List]) -> List[Dict]:
        """
        Приводит любые входные данные к плоскому списку словарей.
        Поддерживает форматы:
        1. {"temp": 25, "hum": 60}
        2. {"temp": {"value": 25, "sensor_type": "T"}, ...}
        3. [{"sensor_id": "temp", "value": 25}, ...]
        """
        result = []
        if isinstance(sensor_data, dict):
            for key, val in sensor_data.items():
                if isinstance(val, dict) and "value" in val:
                    # Сложный объект: {"temp": {"value": 22}}
                    result.append({
                        "sensor_id": key,
                        "sensor_type": val.get("sensor_type", key),
                        "value": val["value"]
                    })
                else:
                    # Простой ключ-значение: {"temp": 22}
                    result.append({
                        "sensor_id": key,
                        "sensor_type": key,
                        "value": val
                    })
        elif isinstance(sensor_data, list):
            result = sensor_data
            
        return result

    def _serialize_payload(self, payload: Any) -> str:
        if isinstance(payload, (dict, list)):
            return json.dumps(payload)
        return str(payload)

    # --- Обертки для безопасного сохранения ---

    async def _safe_save_influx(self, data: list):
        try:
            await self.influx_service.save_sensor_data(data)
        except Exception as e:
            logger.error(f"Failed to save to InfluxDB: {e}")

    async def _safe_save_redis(self, data: list):
        try:
            await self.redis_service.update_cache_from_batch(data)
        except Exception as e:
            logger.error(f"Failed to update Redis cache: {e}")

    # --- Getters ---

    def is_connected(self) -> bool:
        return self._connected