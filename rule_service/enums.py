from enum import Enum as PyEnum


class RuleTriggerType(PyEnum):
    """Defines how a rule is primarily triggered/evaluated."""

    SENSOR_THRESHOLD = "sensor_threshold"
    TIME_BASED = "time_based"
    # Add more later

class RuleActionType(PyEnum):
    """Defines the type of action to be performed."""

    SEND_NOTIFICATION = "send_notification"
    CONTROL_DEVICE = "control_device"
    LOG_EVENT = "log_event"
