import re

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator

from app.enums import TreatmentReason, VehicleStatus


_PHONE_RE = re.compile(r"^05[023458]\d{7}$")
_NAME_RE = re.compile(r"^[A-Za-z\u0590-\u05FF]+ [A-Za-z\u0590-\u05FF]+$")
_PLATE_RE = re.compile(r"^\d{7,8}$")


def _validate_plate(v: str) -> str:
    stripped = re.sub(r"[\s\-]", "", v.strip())
    if not _PLATE_RE.match(stripped):
        raise ValueError("License plate must be exactly 7 or 8 digits")
    return stripped


def _validate_name(v: str) -> str:
    v = v.strip()
    if not _NAME_RE.match(v):
        raise ValueError(
            "Customer name must be exactly two words (Hebrew or English letters) separated by a single space"
        )
    return v


def _validate_phone(v: str) -> str:
    digits = re.sub(r"[\s\-]", "", v.strip())
    if not _PHONE_RE.match(digits):
        raise ValueError(
            "Phone must be exactly 10 digits, start with '05', and the 3rd digit must be 0/2/3/4/5/8"
        )
    return digits


class VehicleCreate(BaseModel):
    license_plate: str
    customer_name: str
    phone_number: str
    reason: TreatmentReason
    status: VehicleStatus = VehicleStatus.ticket_opened

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
    reason: TreatmentReason | None = None

    @field_validator("customer_name")
    @classmethod
    def validate_customer_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("Customer name cannot be set to null")
        return _validate_name(v)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("Phone number cannot be set to null")
        return _validate_phone(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: VehicleStatus | None) -> VehicleStatus | None:
        if v is None:
            raise ValueError("Status cannot be set to null")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: TreatmentReason | None) -> TreatmentReason | None:
        if v is None:
            raise ValueError("Reason cannot be set to null")
        return v


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    license_plate: str
    customer_name: str
    phone_number: str
    status: VehicleStatus
    reason: TreatmentReason
    created_at: AwareDatetime
    updated_at: AwareDatetime
