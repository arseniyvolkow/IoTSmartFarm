import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rule_worker.services.stream_consumer import StreamConsumer

pytestmark = pytest.mark.asyncio

async def test_stream_consumer_listen(mock_redis_service):
    evaluator = AsyncMock()
    consumer = StreamConsumer(mock_redis_service, evaluator)
    
    # We want to run listen_for_sensor_updates, but it has a while True loop.
    # We can mock read_stream_group to raise an exception on the second call to break the loop.
    
    mock_redis_service.read_stream_group.side_effect = [
        # First call: return a valid message
        [
            ("sensor_updates", [
                ("1-0", {"data": json.dumps({"sensor_id": "sensor_1", "value": 25.5})}),
                ("2-0", {"data": json.dumps({"sensor_id": "sensor_1", "value": "not_numeric"})}),
                ("3-0", {"data": "not_json"})
            ])
        ],
        # Second call: empty
        [],
        # Third call: Exception to break loop
        asyncio.CancelledError("break loop")
    ]
    
    mock_db = MagicMock()
    mock_session = AsyncMock()
    mock_db.__aenter__.return_value = mock_session
    
    with patch('rule_worker.services.stream_consumer.get_db', return_value=mock_db):
        try:
            await consumer.listen_for_sensor_updates()
        except asyncio.CancelledError:
            pass
            
    # Evaluator should be called once with 25.5
    evaluator.evaluate_rules_for_sensor.assert_called_once_with("sensor_1", 25.5, mock_session)
    
    # Ack message should be called for valid and invalid
    assert mock_redis_service.ack_message.call_count >= 3
