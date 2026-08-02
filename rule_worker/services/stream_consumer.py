import asyncio
import json
import logging
import os

from rule_worker.database import get_db
from rule_worker.services.redis_service import RedisService
from rule_worker.services.evaluator import RuleEvaluator

logger = logging.getLogger(__name__)


class StreamConsumer:
    """Listen to Redis Streams for real-time sensor updates."""
    def __init__(self, redis_service: RedisService, evaluator: RuleEvaluator):
        self.redis_service = redis_service
        self.evaluator = evaluator

    async def listen_for_sensor_updates(self):
        """Listen to Redis Streams for real-time sensor updates."""
        logger.info("📡 Starting real-time sensor update stream listener...")
        
        stream_name = "sensor_updates"
        group_name = "rule_workers_group"
        consumer_name = f"worker_{os.getpid()}"

        await self.redis_service.ensure_consumer_group(stream_name, group_name)
        
        while True:
            try:
                # Read from the stream
                messages = await self.redis_service.read_stream_group(
                    stream_name=stream_name, 
                    group_name=group_name, 
                    consumer_name=consumer_name, 
                    count=10, 
                    block=2000
                )

                if not messages:
                    continue

                for stream, msg_list in messages:
                    for message_id, msg_data in msg_list:
                        try:
                            # msg_data might be like: {"data": '{"sensor_id": "...", "value": 25.5}'}
                            raw_payload = msg_data.get("data")
                            if raw_payload:
                                logger.info(f"📩 Received sensor update stream msg: {raw_payload}")
                                data = json.loads(raw_payload)
                                sensor_id = data.get("sensor_id")
                                value = data.get("value")
                                
                                if sensor_id is not None and value is not None:
                                    try:
                                        val_float = float(value)
                                        async with get_db() as db_session:
                                            await self.evaluator.evaluate_rules_for_sensor(sensor_id, val_float, db_session)
                                    except ValueError:
                                        logger.warning(f"Received non-numeric value for sensor {sensor_id}: {value}")
                            
                            # Acknowledge the message so it's removed from PEL
                            await self.redis_service.ack_message(stream_name, group_name, message_id)

                        except json.JSONDecodeError:
                            logger.error(f"Failed to decode sensor update message: {msg_data}")
                            # ACK invalid messages to avoid getting stuck
                            await self.redis_service.ack_message(stream_name, group_name, message_id)
                        except Exception as e:
                            logger.error(f"Error processing sensor update: {e}", exc_info=True)
            
            except Exception as e:
                logger.error(f"❌ Error in Stream listener: {e}", exc_info=True)
                await asyncio.sleep(5)
