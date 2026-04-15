import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, String  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Mapped, mapped_column  # pyright: ignore[reportMissingImports]

from app.database import Base


class VehicleStatus(str, enum.Enum):
    IN_INSPECTION = "in_inspection"
    WAITING_PARTS = "waiting_parts"
    IN_PROGRESS = "in_progress"
    READY = "ready"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Vehicle(Base):
    __tablename__ = "vehicles"

    license_plate: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(
        Enum(VehicleStatus), default=VehicleStatus.IN_INSPECTION, nullable=False
    )
    estimated_completion: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )
