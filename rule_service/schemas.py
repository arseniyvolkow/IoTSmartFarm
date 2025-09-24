from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import  datetime
from enum import Enum as PyEnum
from typing import Optional, List

# Rules Models
class RuleTriggerType(PyEnum):
    SENSOR_THRESHOLD = "sensor_threshold"
    # ... other trigger types


class RuleActionType(PyEnum):
    SEND_NOTIFICATION = "send_notification"
    CONTROL_DEVICE = "control_device"
    LOG_EVENT = "log_event"


class RuleActionPayload(BaseModel):
    """A generic model for the action payload (e.g., recipient, MQTT topic)."""

    # Using a catch-all approach as the content is dynamic
    model_config = ConfigDict(extra="allow")


class RuleActionCreate(BaseModel):
    """Model for creating a new action."""

    action_type: RuleActionType
    action_payload: RuleActionPayload
    execution_order: int = 1


class RuleActionRead(RuleActionCreate):
    """Model for reading an action from the database."""

    action_id: str
    rule_id: str
    created_at: datetime


class RuleBase(BaseModel):
    """Base model for shared rule fields."""

    rule_name: str
    description: Optional[str] = None
    trigger_type: RuleTriggerType
    sensor_id: Optional[str] = None
    device_id: Optional[str] = None
    rule_expression: str
    cooldown_seconds: int = 0
    is_active: bool = True


class RuleCreate(RuleBase):
    """Model for creating a new rule."""

    farm_id: str
    actions: List[RuleActionCreate]


class RuleUpdate(BaseModel):
    """Model for updating an existing rule."""

    rule_name: Optional[str] = None
    description: Optional[str] = None
    rule_expression: Optional[str] = None
    cooldown_seconds: Optional[int] = None
    is_active: Optional[bool] = None
    # Note: Trigger type, sensor_id, and device_id are typically not updated directly


class RuleRead(RuleBase):
    """Model for reading a rule from the database."""

    rule_id: str
    farm_id: str
    last_triggered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    actions: List[RuleActionRead] = []

    model_config = ConfigDict(from_attributes=True)

