import asyncio
import logging
import os

import httpx

from rule_worker.database import get_db
from rule_worker.services.action_executor import ActionExecutor
from rule_worker.services.context_builder import RuleContextBuilder
from rule_worker.services.evaluator import RuleEvaluator
from rule_worker.services.redis_service import RedisService
from rule_worker.services.rule_cache import rule_cache
from rule_worker.services.stream_consumer import StreamConsumer

logger = logging.getLogger(__name__)

async def run_cache_reloader(interval_seconds: int = 30):
    """Periodically fetches rules from DB into memory."""
    logger.info(f"🔄 Starting cache reloader (every {interval_seconds}s)")
    while True:
        try:
            await rule_cache.reload_rules()
        except Exception as e:
            logger.error(f"Error in cache reloader task: {e}")
        await asyncio.sleep(interval_seconds)

async def run_periodic_evaluation(evaluator: RuleEvaluator, interval_seconds: int):
    """Run periodic evaluation for time-based rules."""
    logger.info(f"🔄 Starting periodic evaluation (every {interval_seconds}s)")
    while True:
        try:
            async with get_db() as db_session:
                await evaluator.evaluate_all_rules(db_session)
            
            await asyncio.sleep(interval_seconds)
        except Exception as e:
            logger.error(f"Error in periodic evaluation task: {e}")
            await asyncio.sleep(10)

async def run_rule_worker_daemon(interval_seconds: int = 60):
    """
    Run the rule worker with both periodic and real-time evaluation.
    """
    logger.info("🚀 Starting rule worker daemon")

    redis_service = None
    http_client = None

    try:
        # 1. Initialize Redis Service
        redis_service = RedisService(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD"),
        )

        await redis_service.connect()
        logger.info("✅ Redis connected successfully")

        # Create HTTP Client if needed by other services
        http_client = httpx.AsyncClient(timeout=30.0)

        # 2. Initialize Components
        action_executor = ActionExecutor(redis_service)
        context_builder = RuleContextBuilder(redis_service)
        evaluator = RuleEvaluator(action_executor, context_builder)
        stream_consumer = StreamConsumer(redis_service, evaluator)
        
        logger.info("✅ RuleWorker components initialized")

        # 3. Initial load of the cache
        await rule_cache.reload_rules()

        # 4. Start concurrent tasks
        tasks = [
            asyncio.create_task(run_periodic_evaluation(evaluator, interval_seconds)),
            asyncio.create_task(stream_consumer.listen_for_sensor_updates()),
            asyncio.create_task(run_cache_reloader(30))
        ]

        await asyncio.gather(*tasks)

    except asyncio.CancelledError:
        logger.info("⚠️  Daemon tasks cancelled")
    except Exception as e:
        logger.critical(f"🚨 Fatal error in rule worker daemon: {e}", exc_info=True)
        raise

    finally:
        logger.info("\n🧹 Starting cleanup...")
        if http_client:
            await http_client.aclose()
            logger.info("HTTP client closed")
        if redis_service:
            await redis_service.disconnect()
        logger.info("👋 Rule worker daemon shut down complete")