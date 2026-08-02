import asyncio
import logging
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from common.rule_models import Rules, RuleTriggerType
from rule_worker.database import get_db

logger = logging.getLogger(__name__)

class RuleCache:
    def __init__(self):
        self._sensor_rules: Dict[str, List[Rules]] = {}
        self._time_rules: List[Rules] = []
        self._all_rules: List[Rules] = []
        self._lock = asyncio.Lock()

    async def reload_rules(self):
        """Fetch all active rules from the database and update the cache."""
        try:
            async with get_db() as db_session:
                query = select(Rules).options(joinedload(Rules.actions)).where(Rules.is_active == True)
                result = await db_session.execute(query)
                rules = result.scalars().unique().all()
                
                sensor_rules: Dict[str, List[Rules]] = {}
                time_rules: List[Rules] = []
                
                for rule in rules:
                    if rule.trigger_type == RuleTriggerType.SENSOR_THRESHOLD and rule.sensor_id:
                        if rule.sensor_id not in sensor_rules:
                            sensor_rules[rule.sensor_id] = []
                        sensor_rules[rule.sensor_id].append(rule)
                    elif rule.trigger_type == RuleTriggerType.TIME_BASED:
                        time_rules.append(rule)
                        
                async with self._lock:
                    self._sensor_rules = sensor_rules
                    self._time_rules = time_rules
                    self._all_rules = list(rules)
                    
            logger.info(f"🔄 Rule Cache reloaded: {len(self._all_rules)} active rules.")
        except Exception as e:
            logger.error(f"❌ Failed to reload rule cache: {e}")

    async def get_rules_for_sensor(self, sensor_id: str) -> List[Rules]:
        """Get rules for a specific sensor from the cache."""
        async with self._lock:
            return self._sensor_rules.get(sensor_id, []).copy()

    async def get_time_rules(self) -> List[Rules]:
        """Get all time-based rules from the cache."""
        async with self._lock:
            return self._time_rules.copy()
            
    async def get_all_rules(self, trigger_type: Optional[RuleTriggerType] = None) -> List[Rules]:
        """Get all active rules, optionally filtered by trigger type."""
        async with self._lock:
            if trigger_type == RuleTriggerType.SENSOR_THRESHOLD:
                rules = []
                for s_rules in self._sensor_rules.values():
                    rules.extend(s_rules)
                return rules
            elif trigger_type == RuleTriggerType.TIME_BASED:
                return self._time_rules.copy()
            return self._all_rules.copy()

# Global singleton for the cache
rule_cache = RuleCache()
