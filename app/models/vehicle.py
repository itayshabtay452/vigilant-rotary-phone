from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, String  # pyright: ignore[reportMissingImports]
from sqlalchemy import types  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Mapped, mapped_column  # pyright: ignore[reportMissingImports]

from app.database import Base
from app.enums import VehicleStatus


class _UTCDateTime(types.TypeDecorator):  # type: ignore[type-arg]
    """DateTime that always stores as naive UTC and returns UTC-aware on read.

    SQLite silently drops timezone info from DateTime(timezone=True), so this
    decorator normalises the round-trip for every backend consistently.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:  # type: ignore[override]
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                f"Naive datetime {value!r} passed to _UTCDateTime column. "
                "Provide a timezone-aware datetime (e.g. datetime.now(timezone.utc))."
            )
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:  # type: ignore[override]
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


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
        _UTCDateTime(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        _UTCDateTime(), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        _UTCDateTime(), default=_utc_now, onupdate=_utc_now, nullable=False
    )
