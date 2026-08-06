#!/bin/bash

echo "Starting test runs across all Docker containers..."

# List of services to test
services=("user_service" "farm_management_service" "rule_service" "sensor_data_service" "rule_worker")

for service in "${services[@]}"; do
    echo "========================================================"
    echo "Running tests for $service..."
    echo "========================================================"
    
    # 1. Install test dependencies on the fly inside the container
    docker compose exec -T $service sh -c "pip install --quiet pytest pytest-asyncio pytest-cov pytest-mock httpx fakeredis aiosqlite rule-engine pytest-timeout"
    
    # 2. Run pytest targeting only that service's tests with pytest-timeout to prevent infinite hangs
    docker compose exec -T $service sh -c "python -m pytest $service/tests --timeout=20" || true
done

echo "All tests finished!"
