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
        "פתחנו עבורכם כרטיס שירות לרכב. נעדכן אתכם בהתקדמות."
    ),
    VehicleStatus.mechanics: "המוסכניקים שלנו מטפלים ברכב כעת.",
    VehicleStatus.in_test: "הרכב נמצא בנסיעת מבחן לאימות התיקון.",
    VehicleStatus.washing: "הרכב עובר שטיפה — השלב האחרון לפני האיסוף.",
    VehicleStatus.ready_for_payment: (
        "הרכב מוכן. נא להסדיר את התשלום כדי שנוכל למסור אותו."
    ),
    VehicleStatus.ready: "בשורה טובה! הרכב מוכן לאיסוף.",
}

_GENERIC_STATUS_COPY: Final[str] = "הרכב נמצא כעת בטיפולנו."

NON_TEXT_REPLY: Final[str] = "נא לשלוח את לוחית הרישוי כהודעת טקסט."
INVALID_PLATE_REPLY: Final[str] = (
    "הלוחית שנשלחה אינה תקינה. נא לשלוח 7 או 8 ספרות, למשל 1234567."
)


def status_copy(status: VehicleStatus) -> str:
    return STATUS_MESSAGES.get(status, _GENERIC_STATUS_COPY)


def format_vehicle_status(vehicle: Vehicle) -> str:
    return (
        f"שלום {vehicle.customer_name},\n"
        f"סטטוס לוחית {vehicle.license_plate}: {status_copy(vehicle.status)}\n"
        "— המוסך"
    )


def format_not_found(plate: str) -> str:
    return (
        f"לא הצלחנו לאתר רכב עם לוחית {plate}. "
        "נא לבדוק שוב או להתקשר אלינו."
    )
