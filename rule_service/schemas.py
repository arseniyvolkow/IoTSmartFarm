from datetime import datetime

from pydantic import BaseModel, ConfigDict

from common.models.rule_enums import *


class RuleActionPayload(BaseModel):
    """A generic model for the action payload (e.g., recipient, MQTT topic)."""

    # Add this configuration to explicitly allow any extra keys/values
    # that are not defined as fields in the model.
    model_config = ConfigDict(extra='allow') 


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
    description: str | None = None
    trigger_type: RuleTriggerType
    sensor_id: str | None = None
    device_id: str | None = None
    rule_expression: str
    cooldown_seconds: int = 0
    is_active: bool = True


class RuleCreate(RuleBase):
    """Model for creating a new rule."""

    farm_id: str
    actions: list[RuleActionCreate]


class RuleUpdate(BaseModel):
    """Model for updating an existing rule."""

    rule_name: str | None = None
    description: str | None = None
    rule_expression: str | None = None
    cooldown_seconds: int | None = None
    is_active: bool | None = None
    # Note: Trigger type, sensor_id, and device_id are typically not updated directly


class RuleRead(RuleBase):
    """Model for reading a rule from the database."""

    rule_id: str
    farm_id: str
    last_triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    actions: list[RuleActionRead] = []

    model_config = ConfigDict(from_attributes=True)

