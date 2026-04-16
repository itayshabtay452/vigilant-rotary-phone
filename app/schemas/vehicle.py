import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class VehicleStatus(str, Enum):
    IN_INSPECTION = "in_inspection"
    WAITING_PARTS = "waiting_parts"
    IN_PROGRESS = "in_progress"
    READY = "ready"


def _validate_plate(v: str) -> str:
    v = v.strip().upper()
    stripped = re.sub(r"[\s\-]", "", v)
    if not re.match(r"^[A-Z0-9]{5,10}$", stripped):
        raise ValueError("License plate must be 5–10 alphanumeric characters (hyphens allowed)")
    return v


def _validate_name(v: str) -> str:
    v = v.strip()
    if len(v) < 2:
        raise ValueError("Customer name must be at least 2 characters")
    return v


def _validate_phone(v: str) -> str:
    v = v.strip()
    digits = re.sub(r"[\s\-\+\(\)]", "", v)
    if not re.match(r"^\d{9,15}$", digits):
        raise ValueError("Phone number must be 9–15 digits (e.g. +972501234567 or 0501234567)")
    return v


class VehicleCreate(BaseModel):
    license_plate: str
    customer_name: str
    phone_number: str
    status: VehicleStatus = VehicleStatus.IN_INSPECTION
    estimated_completion: datetime | None = None

    @field_validator("license_plate")
    @classmethod
    def validate_license_plate(cls, v: str) -> str:
        return _validate_plate(v)

    @field_validator("customer_name")
    @classmethod
    def validate_customer_name(cls, v: str) -> str:
        return _validate_name(v)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        return _validate_phone(v)


class VehicleUpdate(BaseModel):
    customer_name: str | None = None
    phone_number: str | None = None
    status: VehicleStatus | None = None
    estimated_completion: datetime | None = None

    @field_validator("customer_name")
    @classmethod
    def validate_customer_name(cls, v: str | None) -> str | None:
        return _validate_name(v) if v is not None else None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        return _validate_phone(v) if v is not None else None


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    license_plate: str
    customer_name: str
    phone_number: str
    status: VehicleStatus
    estimated_completion: datetime | None
    created_at: datetime
    updated_at: datetime | None
