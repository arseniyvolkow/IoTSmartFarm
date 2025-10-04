# rule_worker.py
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import httpx
import rule_engine
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from database import get_db
from models import Rules, RuleActionType, RuleTriggerType
from services.redis_service import RedisService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RuleWorker:
    def __init__(self, redis_service: Optional[RedisService] = None):
        self.redis_service = redis_service
        self.http_client = None
        self._owns_redis_service = redis_service is None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Initialize Redis service if not provided
        if self.redis_service is None:
            try:
                self.redis_service = RedisService(
                    host=os.getenv('REDIS_HOST', 'localhost'),
                    port=int(os.getenv('REDIS_PORT', 6379)),
                    db=int(os.getenv('REDIS_DB', 0)),
                    password=os.getenv('REDIS_PASSWORD')
                )
                await self.redis_service.connect()
                logger.info("Connected to Redis successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.redis_service = None
        elif not self.redis_service.is_connected():
            # If Redis service was provided but not connected, try to connect
            try:
                await self.redis_service.connect()
                logger.info("Connected to Redis successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.http_client:
            await self.http_client.aclose()
        
        # Only disconnect Redis if we own the service
        if self._owns_redis_service and self.redis_service:
            await self.redis_service.disconnect()

    async def fetch_latest_sensor_data_from_redis(self, sensor_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest sensor data from Redis using RedisService"""
        if not self.redis_service or not self.redis_service.is_connected():
            logger.error("Redis service not available or not connected")
            return None
            
        try:
            sensor_value = await self.redis_service.get_sensor_value(sensor_id)
            
            if sensor_value is None:
                return None
            
            # Try to parse as JSON first, then as numeric, finally as string
            try:
                data = json.loads(sensor_value)
                if isinstance(data, dict):
                    return data
                else:
                    return {"value": data}
            except (json.JSONDecodeError, TypeError):
                # If it's not JSON, try numeric conversion
                try:
                    numeric_value = float(sensor_value)
                    return {"value": numeric_value}  # FIXED: Always return dict format
                except ValueError:
                    return {"value": sensor_value}  # FIXED: Always return dict format
                    
        except Exception as e:
            logger.error(f"Error fetching sensor data for {sensor_id}: {e}")
            return None

    def _extract_sensor_value(self, sensor_data: Any) -> Optional[float]:
        """
        Extract a numeric value from sensor data.
        Handles various data formats: dict, numeric, string.
        """
        try:
            # If already numeric, return as float
            if isinstance(sensor_data, (int, float)):
                return float(sensor_data)
            
            # If it's a dict, try common keys
            if isinstance(sensor_data, dict):
                # Try common value keys
                for key in ['value', 'sensor_value', 'reading', 'measurement', 'data', 'moisture', 'humidity', 'temperature']:
                    if key in sensor_data:
                        value = sensor_data[key]
                        if isinstance(value, (int, float)):
                            return float(value)
                        # Try to convert string to float
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            continue
                
                # If no common keys found, log available keys for debugging
                logger.debug(f"Could not find numeric value in dict. Available keys: {list(sensor_data.keys())}")
                return None
            
            # If it's a string, try to convert to float
            if isinstance(sensor_data, str):
                try:
                    return float(sensor_data)
                except ValueError:
                    logger.debug(f"Could not convert string to float: {sensor_data}")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting sensor value: {e}")
            return None
    

    async def execute_action(self, action_dict: Dict[str, Any], rule_context: Dict[str, Any]) -> bool:
        """Execute a rule action based on its type"""
        action_type = action_dict.get("action_type")
        action_payload = action_dict.get("action_payload", {})
        action_id = action_dict.get("action_id")
        
        logger.info(f"Executing action {action_id} of type {action_type}")
        
        try:
            if action_type == RuleActionType.CONTROL_DEVICE:
                return await self._execute_device_control(action_payload, rule_context)
            elif action_type == RuleActionType.SEND_NOTIFICATION:
                return await self._execute_email_notification(action_payload, rule_context)
            elif action_type == RuleActionType.LOG_EVENT:
                return await self._execute_log_message(action_payload, rule_context)
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False
        except Exception as e:
            logger.error(f"Error executing action {action_id}: {e}")
            return False

    async def _execute_device_control(self, action_payload: Dict[str, Any], context: Dict[str, Any]) -> bool:
        base_url = os.getenv('SENSOR_DATA_SERVICE_HOST', 'http://sensor_data_service:8000') 
        url = f"{base_url}/actuator-mode-update"
        
        # FIX: Use 'devices_to_control' to match your payload structure
        devices = action_payload.get('devices_to_control', [])
        
        # Transform to the format expected by sensor_data_service
        control_payload = {
            "actuators_to_control": devices  # sensor_data_service expects this key
        }        
        print(control_payload)
        logger.info(f"Attempting control action to {url} with payload: {control_payload}") # <-- NEW LOG

        try:
            # 2. Add an explicit HTTPX client instantiation/context if not using a shared one
            # If self.http_client is a shared client, ensure it's kept alive long enough.
            
            response = await self.http_client.post(
                url,
                json=control_payload,
                timeout=5.0
            )
            response.raise_for_status()
            
            # This log confirms success and status
            logger.info(f"SUCCESS: Device control request sent. Status: {response.status_code}")
            return True

        except httpx.RequestError as e:
            logger.error(f"FAILURE: HTTP request to Sensor Data Service failed: {e}")
            return False
        except httpx.HTTPStatusError as e:
            # This will catch 4xx or 5xx from the sensor-data-service
            logger.error(f"FAILURE: HTTP error response: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"FAILURE: Unexpected error in device control: {e}")
            return False

    # async def _execute_http_request(self, payload: Dict[str, Any], context: Dict[str, Any]) -> bool:
    #     """Execute HTTP request action"""
    #     url = payload.get("url")
    #     method = payload.get("method", "POST").upper()
    #     headers = payload.get("headers", {})
    #     data = payload.get("data", {})
        
    #     if not url:
    #         logger.error("HTTP request action missing URL")
    #         return False
        
    #     # Replace placeholders in data with context values
    #     data = self._replace_placeholders(data, context)
        
    #     try:
    #         response = await self.http_client.request(
    #             method=method,
    #             url=url,
    #             headers=headers,
    #             json=data if method in ["POST", "PUT", "PATCH"] else None,
    #             params=data if method == "GET" else None
    #         )
    #         response.raise_for_status()
    #         logger.info(f"HTTP request successful: {response.status_code}")
    #         return True
    #     except httpx.RequestError as e:
    #         logger.error(f"HTTP request failed: {e}")
    #         return False
    #     except httpx.HTTPStatusError as e:
    #         logger.error(f"HTTP error response: {e.response.status_code} - {e.response.text}")
    #         return False

    # async def _execute_email_notification(self, payload: Dict[str, Any], context: Dict[str, Any]) -> bool:
    #     """Execute email notification action"""
    #     # This is a placeholder - implement based on your email service
    #     to_email = payload.get("to")
    #     subject = payload.get("subject", "Rule Alert")
    #     body = payload.get("body", "A rule has been triggered")
        
    #     logger.info(f"Email notification: To={to_email}, Subject={subject}")
    #     # TODO: Implement actual email sending logic
    #     return True

    # async def _execute_webhook(self, payload: Dict[str, Any], context: Dict[str, Any]) -> bool:
    #     """Execute webhook action"""
    #     return await self._execute_http_request(payload, context)

    # async def _execute_log_message(self, payload: Dict[str, Any], context: Dict[str, Any]) -> bool:
    #     """Execute log message action"""
    #     message = payload.get("message", "Rule triggered")
    #     level = payload.get("level", "INFO").upper()
    #     if level == "ERROR":
    #         logger.error(message)
    #     elif level == "WARNING":
    #         logger.warning(message)
    #     elif level == "DEBUG":
    #         logger.debug(message)
    #     else:
    #         logger.info(message)
        
    #     return True


    async def update_rule_last_triggered(self, db_session, rule_id: int):
        """Update the last_triggered_at timestamp for a rule"""
        try:
            stmt = (
                update(Rules)
                .where(Rules.rule_id == rule_id)
                .values(last_triggered_at=datetime.now())
            )
            await db_session.execute(stmt)
            await db_session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Failed to update last_triggered_at for rule {rule_id}: {e}")
            await db_session.rollback()
            raise

    async def evaluate_single_rule(self, rule, db_session) -> bool:
        """Evaluate a single rule and execute actions if matched"""
        rule_id = rule.rule_id
        rule_name = rule.rule_name
        sensor_id = rule.sensor_id
        rule_expression_str = rule.rule_expression
        cooldown_seconds = rule.cooldown_seconds
        last_triggered_at = rule.last_triggered_at
        trigger_type = rule.trigger_type
        actions_data = rule.actions

        # Check cooldown - fix timezone issue
        if last_triggered_at:
            # Ensure both timestamps are timezone-aware or naive
            now = datetime.now()
            if last_triggered_at.tzinfo is not None:
                # If last_triggered_at has timezone info, make now timezone-aware
                from datetime import timezone
                now = now.replace(tzinfo=timezone.utc)
            
            time_since_triggered = now - last_triggered_at
            if time_since_triggered < timedelta(seconds=cooldown_seconds):
                logger.debug(f"Rule '{rule_name}' (ID: {rule_id}) on cooldown. Skipping.")
                return False

        rule_context = {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "sensor_id": sensor_id,
            "current_time": datetime.now().isoformat(),
        }

        try:
            is_ready_to_evaluate = False
            
            if trigger_type == RuleTriggerType.SENSOR_THRESHOLD and sensor_id:
                sensor_data = await self.fetch_latest_sensor_data_from_redis(sensor_id)
                if sensor_data is None:
                    logger.warning(f"No data found in Redis for sensor {sensor_id}. Skipping rule evaluation.")
                    return False
                
                # Extract numeric value from sensor data
                sensor_value = self._extract_sensor_value(sensor_data)
                if sensor_value is None:
                    logger.warning(f"Could not extract numeric value from sensor data for {sensor_id}. Data: {sensor_data}")
                    return False
                
                # Add numeric value to context with multiple variable names for flexibility
                rule_context["value"] = sensor_value  # Primary short name
                rule_context["sensor_value"] = sensor_value  # Descriptive name
                rule_context[sensor_id] = sensor_value  # UUID as fallback
                
                # Also add the full sensor data if it's a dict (for advanced rules)
                if isinstance(sensor_data, dict):
                    rule_context["sensor_data"] = sensor_data
                
                logger.debug(f"Sensor {sensor_id} value: {sensor_value}, Full data: {sensor_data}")
                is_ready_to_evaluate = True
                
            elif trigger_type == RuleTriggerType.TIME_BASED:
                # Add time-based context
                now = datetime.now()
                rule_context.update({
                    "hour": now.hour,
                    "minute": now.minute,
                    "day_of_week": now.weekday(),
                    "day": now.day,
                    "month": now.month,
                    "year": now.year,
                })
                is_ready_to_evaluate = True

            if not is_ready_to_evaluate:
                logger.warning(f"Skipping rule '{rule_name}' due to unsupported trigger type or missing context.")
                return False

            # Evaluate rule expression
            logger.debug(f"Evaluating rule '{rule_name}' with expression: {rule_expression_str}")
            logger.debug(f"Rule context: {rule_context}")
            
            rule_engine_obj = rule_engine.Rule(rule_expression_str)
            if rule_engine_obj.matches(rule_context):
                logger.info(f"Rule '{rule_name}' (ID: {rule_id}) matched! Context: {rule_context}")

                # Sort actions by execution order
                sorted_actions = sorted(actions_data, key=lambda x: x.execution_order or 0)
                
                # Execute actions
                action_results = []
                logger.info(f"Executing {len(sorted_actions)} actions for rule '{rule_name}'")

                for action_data in sorted_actions:
                    action_dict = {
                        "action_id": action_data.action_id,
                        "action_type": action_data.action_type,
                        "action_payload": action_data.action_payload,
                        "execution_order": action_data.execution_order,
                    }
                    
                    logger.info(f"Processing action {action_dict['action_id']} of type {action_dict['action_type']}")
                    
                    try:
                        success = await self.execute_action(action_dict, rule_context)
                        action_results.append(success)
                        if not success:
                            logger.warning(f"Action {action_dict.get('action_id')} failed")
                    except Exception as action_e:
                        logger.error(f"Error executing action: {action_e}", exc_info=True)
                        action_results.append(False)
                # Update last triggered timestamp
                await self.update_rule_last_triggered(db_session, rule_id)
                logger.info(f"Rule '{rule_name}' (ID: {rule_id}) last_triggered_at updated.")
                
                return True
            else:
                logger.debug(f"Rule '{rule_name}' (ID: {rule_id}) did not match. Context: {rule_context}")
                return False

        except rule_engine.errors.RuleSyntaxError as e:
            logger.error(f"Rule '{rule_name}' (ID: {rule_id}) has a syntax error: {e}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during evaluation of rule '{rule_name}': {e}", exc_info=True)
            return False
        

    async def evaluate_rules(self):
        """Main function to evaluate all active rules in the database."""
        logger.info(f"[{datetime.now().isoformat()}] Starting rule evaluation cycle...")
        
        if not self.redis_service or not self.redis_service.is_connected():
            logger.error("Redis service not available or not connected. Skipping rule evaluation cycle.")
            return

        try:
            async with get_db() as db_session:
                # Query active rules with their actions
                query = (
                    select(Rules)
                    .options(joinedload(Rules.actions))
                    .filter(Rules.is_active == True)
                )

                try:
                    result = await db_session.execute(query)
                    rules = result.scalars().unique().all()
                except SQLAlchemyError as e:
                    logger.error(f"Database query failed: {e}")
                    return

                if not rules:
                    logger.info("No active rules found. Skipping evaluation.")
                    return

                logger.info(f"Found {len(rules)} active rules to evaluate")
                
                # Evaluate each rule
                evaluated_count = 0
                triggered_count = 0
                
                for rule in rules:
                    try:
                        was_triggered = await self.evaluate_single_rule(rule, db_session)
                        evaluated_count += 1
                        if was_triggered:
                            triggered_count += 1
                    except Exception as e:
                        logger.error(f"Failed to evaluate rule {rule.rule_id}: {e}", exc_info=True)

                logger.info(f"Rule evaluation completed. Evaluated: {evaluated_count}, Triggered: {triggered_count}")

        except Exception as e:
            logger.error(f"Critical error in rule evaluation cycle: {e}", exc_info=True)
        finally:
            logger.info(f"[{datetime.now().isoformat()}] Rule evaluation cycle finished.")


# Factory function to create and configure RuleWorker
async def create_rule_worker(redis_service: Optional[RedisService] = None) -> RuleWorker:
    """Create a configured RuleWorker instance"""
    return RuleWorker(redis_service=redis_service)


# # Main execution function
# async def run_rule_evaluation_cycle(redis_service: Optional[RedisService] = None):
#     """Run a single rule evaluation cycle"""
#     async with RuleWorker(redis_service=redis_service) as rule_worker:
#         await rule_worker.evaluate_rules()


async def run_rule_worker_daemon(interval_seconds: int = 60, redis_service: Optional[RedisService] = None):
    """Run the rule worker continuously with specified interval, managing the worker lifecycle."""
    logger.info(f"Starting rule worker daemon with {interval_seconds}s interval")
    
    # Use the context manager OUTSIDE the while loop to manage the client/redis lifecycle once
    async with RuleWorker(redis_service=redis_service) as rule_worker:
        
        while True:
            try:
                # 1. Execute the main work directly
                # This calls the evaluate_rules method on the active worker instance
                await rule_worker.evaluate_rules()
                
                # 2. Log status and pause
                logger.info(f"Rule evaluation cycle complete. Sleeping for {interval_seconds} seconds...")
                await asyncio.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Rule worker daemon stopped by user")
                break
            except Exception as e:
                # Log critical errors, but keep the worker alive
                logger.error(f"Error in rule worker daemon loop: {e}", exc_info=True)
                await asyncio.sleep(10) # Pause before next attempt

if __name__ == "__main__":
    # Get the interval from environment variable, defaulting to 60 seconds
    interval = int(os.getenv('RULE_EVALUATION_INTERVAL', 60))
    
    # 🚨 CRITICAL FIX: Call the continuous daemon function
    asyncio.run(run_rule_worker_daemon(interval_seconds=interval))