import asyncio
import os
from .rule_worker import run_rule_worker_daemon

if __name__ == "__main__":
    interval = int(os.getenv('RULE_EVALUATION_INTERVAL', 60))
    asyncio.run(run_rule_worker_daemon(interval_seconds=interval))