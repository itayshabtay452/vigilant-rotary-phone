"""Customer-facing WhatsApp reply templates.

All user-visible copy lives here so translation / tone changes never force
edits to business logic or the HTTP layer.
"""
from __future__ import annotations

from typing import Final

from app.enums import VehicleStatus
from app.models.vehicle import Vehicle

STATUS_MESSAGES: Final[dict[VehicleStatus, str]] = {
    VehicleStatus.ticket_opened: (
        "We've opened a service ticket for your vehicle. We'll keep you posted."
    ),
    VehicleStatus.mechanics: "Our mechanics are working on your vehicle right now.",
    VehicleStatus.in_test: "Your vehicle is being road-tested to verify the repair.",
    VehicleStatus.washing: "Your vehicle is being washed — the last step before pickup.",
    VehicleStatus.ready_for_payment: (
        "Your vehicle is ready. Please settle payment so we can hand it over."
    ),
    VehicleStatus.ready: "Great news! Your vehicle is ready for pickup.",
}

_GENERIC_STATUS_COPY: Final[str] = "Your vehicle is currently in our care."

NON_TEXT_REPLY: Final[str] = "Please send your license plate as a text message."
INVALID_PLATE_REPLY: Final[str] = (
    "That doesn't look like a valid license plate. "
    "Please send 7 or 8 digits, e.g. 1234567."
)


def status_copy(status: VehicleStatus) -> str:
    return STATUS_MESSAGES.get(status, _GENERIC_STATUS_COPY)


def format_vehicle_status(vehicle: Vehicle) -> str:
    return (
        f"Hi {vehicle.customer_name},\n"
        f"Status for plate {vehicle.license_plate}: {status_copy(vehicle.status)}\n"
        "— Garage"
    )


def format_not_found(plate: str) -> str:
    return (
        f"We couldn't find a vehicle with plate {plate}. "
        "Please double-check and try again, or call us."
    )
