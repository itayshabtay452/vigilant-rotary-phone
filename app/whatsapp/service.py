"""Pure business logic for handling inbound WhatsApp messages.

No FastAPI, no HTTP, no Green-API imports — this module is trivially testable
against the existing in-memory SQLite fixture.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final

from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle
from app.whatsapp.formatting import (
    INVALID_PLATE_REPLY,
    NON_TEXT_REPLY,
    format_not_found,
    format_vehicle_status,
)

_LOGGER = logging.getLogger(__name__)

_PLATE_RE: Final[re.Pattern[str]] = re.compile(r"^\d{7,8}$")
_GROUP_CHAT_SUFFIX: Final[str] = "@g.us"
_DIRECT_CHAT_SUFFIX: Final[str] = "@c.us"
_IL_COUNTRY_CODE: Final[str] = "972"


@dataclass(frozen=True, slots=True)
class IncomingMessageResult:
    """Outcome of processing one inbound message.

    Attributes:
        reply: The message body to send back, or ``None`` if we must stay
            silent (group chats, unknown webhook types, empty chat id).
        skipped_reason: Human-readable note for logs/metrics when ``reply``
            is ``None``.
    """

    reply: str | None
    skipped_reason: str | None = None


def _normalize_plate(text: str) -> str:
    """Strip all non-digit characters.

    Mirrors the server-side rule (`^\\d{7,8}$`) and the primary-key form used
    by ``Vehicle.license_plate``.
    """
    return re.sub(r"\D", "", text)


def _is_group_chat(chat_id: str) -> bool:
    return chat_id.endswith(_GROUP_CHAT_SUFFIX)


def _stored_phone_to_chat_id(phone_number: str) -> str:
    """Convert a stored Israeli `05XXXXXXXX` phone number into Green-API's
    `<msisdn>@c.us` form so we can compare it to the webhook's ``chatId``.

    We only strip non-digits and replace a leading ``0`` with the country
    code; anything else is passed through untouched so callers can still
    compare raw strings when the format is unexpected.
    """
    digits = re.sub(r"\D", "", phone_number)
    if digits.startswith("0"):
        digits = _IL_COUNTRY_CODE + digits[1:]
    return f"{digits}{_DIRECT_CHAT_SUFFIX}"


def _log_phone_mismatch(plate: str, chat_id: str, stored_phone: str) -> None:
    expected_chat_id = _stored_phone_to_chat_id(stored_phone)
    if chat_id == expected_chat_id:
        return
    _LOGGER.warning(
        "Phone number mismatch for plate %s: sender is %s, but DB has %s",
        plate,
        chat_id,
        stored_phone,
    )


def handle_incoming_message(
    chat_id: str | None,
    text: str | None,
    db: Session,
) -> IncomingMessageResult:
    """Resolve a (chat_id, text) pair into a reply to send, if any."""
    if not chat_id:
        return IncomingMessageResult(reply=None, skipped_reason="missing chat_id")

    if _is_group_chat(chat_id):
        _LOGGER.info("Ignoring group-chat message from %s", chat_id)
        return IncomingMessageResult(reply=None, skipped_reason="group_chat")

    if text is None or not text.strip():
        return IncomingMessageResult(reply=NON_TEXT_REPLY, skipped_reason=None)

    plate = _normalize_plate(text)
    if not _PLATE_RE.match(plate):
        return IncomingMessageResult(reply=INVALID_PLATE_REPLY, skipped_reason=None)

    vehicle = db.get(Vehicle, plate)
    if vehicle is None:
        return IncomingMessageResult(reply=format_not_found(plate), skipped_reason=None)

    # Impersonation / contact-change canary: log only, never block the reply.
    _log_phone_mismatch(plate, chat_id, vehicle.phone_number)

    return IncomingMessageResult(reply=format_vehicle_status(vehicle), skipped_reason=None)
