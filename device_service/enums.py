from enum import Enum as PyEnum

class ActuatorState(PyEnum):
    ON = "on"
    OFF = "off"
    PAUSED = "paused"
    ERROR = "error"
    IDLE = "idle"

class DeviceStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"