from pydantic import BaseModel
from typing import List


class ActuatorControl(BaseModel):
    actuator_id: str
    command: dict


class ActuatorPayload(BaseModel):
    actuators_to_control: List[ActuatorControl]