from pydantic import BaseModel, Field
from typing import List

# --- Actuator Schemas (No changes needed) ---

class ActuatorControl(BaseModel):
    actuator_id: str
    command: str


class ActuatorPayload(BaseModel):
    actuators_to_control: List[ActuatorControl]

# --- Sensor Schemas (Modified) ---

class SensorReading(BaseModel):
    """Schema for a single sensor reading."""

    sensor_id: str = Field(
        ..., description="Unique ID for the sensor (e.g., 'temp_kitchen')."
    )
    sensor_type: str = Field(
        ..., description="Generic type of the sensor (e.g., 'temperature')."
    )
    value: float = Field(..., description="The sensor's measured value.")


class SensorDataBatch(BaseModel):
    """
    Schema for a batch of sensor readings.
    The device_id is no longer included as it's not saved to the database.
    """
    # MODIFIED: Removed the device_id field
    sensors: List[SensorReading] = Field(..., description="A list of sensor readings.")