from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class VehicleStatus(str, Enum):
    IN_INSPECTION = "in_inspection"
    WAITING_PARTS = "waiting_parts"
    IN_PROGRESS = "in_progress"
    READY = "ready"


class VehicleCreate(BaseModel):
    license_plate: str
    customer_name: str
    phone_number: str
    status: VehicleStatus = VehicleStatus.IN_INSPECTION
    estimated_completion: datetime | None = None


class VehicleUpdate(BaseModel):
    customer_name: str | None = None
    phone_number: str | None = None
    status: VehicleStatus | None = None
    estimated_completion: datetime | None = None


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    license_plate: str
    customer_name: str
    phone_number: str
    status: VehicleStatus
    estimated_completion: datetime | None
    created_at: datetime
    updated_at: datetime | None
