from rule_worker import run_rule_worker_daemon
import asyncio
import os
import sys
import logging


# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout  # Ensure logs go to stdout for Docker
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Load the rule evaluation interval from environment variables
    try:
        interval = int(os.getenv('RULE_EVALUATION_INTERVAL', 60))
        if interval <= 0:
            raise ValueError("Interval must be a positive integer.")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid RULE_EVALUATION_INTERVAL: {e}. Defaulting to 60s.")
        interval = 60
    
    logger.info(f"🚀 Starting Rule Worker Daemon with {interval}s interval")
    
    try:
        # Start the main continuous execution loop
        asyncio.run(run_rule_worker_daemon(interval_seconds=interval))
    except KeyboardInterrupt:
        logger.info("⚠️  Rule Worker Daemon received interrupt signal - shutting down")
    except Exception as e:
        logger.critical(f"🚨 Rule Worker Daemon crashed: {e}", exc_info=True)
        sys.exit(1)