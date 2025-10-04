import asyncio
import os
import sys
import logging

# Assuming your worker entry file is named main.py and is in the same directory 
# or a level above rule_worker.py. Adjust the import path as necessary.
# If rule_worker.py is in the root directory:
# from rule_worker import run_rule_worker_daemon 

# If rule_worker.py is inside a 'rule_worker' package/directory:
from rule_worker import run_rule_worker_daemon 

# Configure logging early (optional, but good practice)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout # Ensure logs go to stdout for Docker
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Load the rule evaluation interval from the environment variables, 
    # defaulting to 60 seconds if not set.
    try:
        interval = int(os.getenv('RULE_EVALUATION_INTERVAL', 60))
        if interval <= 0:
            raise ValueError("Interval must be a positive integer.")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid RULE_EVALUATION_INTERVAL setting: {e}. Defaulting to 60s.")
        interval = 60
        
    logger.info(f"Starting Rule Worker Daemon with an interval of {interval} seconds.")
    
    try:
        # 🚀 Start the main continuous execution loop
        asyncio.run(run_rule_worker_daemon(interval_seconds=interval))
        
    except KeyboardInterrupt:
        # This handles CTRL+C or clean signal from Docker stop
        logger.info("Rule Worker Daemon received interrupt signal and is shutting down.")
    except Exception as e:
        # Catch any exceptions that escape the daemon's internal loop
        logger.critical(f"Rule Worker Daemon crashed: {e}", exc_info=True)
        # Allow the container to exit with a non-zero code to indicate failure
        sys.exit(1)