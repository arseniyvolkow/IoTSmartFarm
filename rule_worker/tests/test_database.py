from unittest.mock import AsyncMock, patch

import pytest

from rule_worker.database import get_db

pytestmark = pytest.mark.asyncio


async def test_get_db_success():
    with patch("rule_worker.database.AsyncSessionLocal") as mock_session_local:
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        async with get_db() as session:
            assert session == mock_session

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()


async def test_get_db_error():
    with patch("rule_worker.database.AsyncSessionLocal") as mock_session_local:
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        with pytest.raises(ValueError):
            async with get_db() as session:
                raise ValueError("error")

        mock_session.commit.assert_not_called()
        mock_session.rollback.assert_called_once()
