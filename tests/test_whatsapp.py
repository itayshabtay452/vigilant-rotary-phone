"""Tests for the WhatsApp integration: schema, service, and webhook endpoint.

Follows the same fixture style as tests/test_vehicles.py (TestClient with an
in-memory SQLite), and stubs the Green-API client so no real HTTP is fired.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.enums import VehicleStatus
from app.routers import whatsapp as whatsapp_router
from app.whatsapp import client as whatsapp_client
from app.whatsapp.client import GreenApiClient
from app.whatsapp.formatting import (
    INVALID_PLATE_REPLY,
    NON_TEXT_REPLY,
    STATUS_MESSAGES,
    format_not_found,
    format_vehicle_status,
)
from app.whatsapp.schemas import parse_webhook
from app.whatsapp.service import handle_incoming_message

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_VALID_PLATE = "1234567"
_VALID_PAYLOAD: dict = {
    "license_plate": _VALID_PLATE,
    "customer_name": "Jane Doe",
    "phone_number": "0501234567",
    "reason": "annual",
}


class _FakeClient:
    """Captures every outbound send instead of hitting the network."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.sent: list[tuple[str, str]] = []

    async def send_message(self, chat_id: str, message: str) -> bool:
        self.sent.append((chat_id, message))
        return True


@pytest.fixture
def fake_client() -> Iterator[_FakeClient]:
    client = _FakeClient()
    whatsapp_client.set_client(client)  # type: ignore[arg-type]
    whatsapp_router._reset_dedupe_cache_for_tests()
    try:
        yield client
    finally:
        whatsapp_client.set_client(None)
        whatsapp_router._reset_dedupe_cache_for_tests()


@pytest.fixture(autouse=True)
def _clear_webhook_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to no-auth webhook so the token header is optional per test."""
    monkeypatch.setattr(
        "app.routers.whatsapp.settings.GREEN_API_WEBHOOK_TOKEN", "", raising=False
    )


def _create_vehicle(
    client: TestClient,
    overrides: dict | None = None,
) -> dict:
    payload = {**_VALID_PAYLOAD, **(overrides or {})}
    r = client.post("/vehicles/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _incoming_payload(
    *,
    text: str | None = "1234567",
    chat_id: str = "972541234567@c.us",
    id_message: str = "MSG-1",
    type_message: str = "textMessage",
    type_webhook: str = "incomingMessageReceived",
) -> dict:
    if type_message == "textMessage":
        message_data: dict = {
            "typeMessage": "textMessage",
            "textMessageData": {"textMessage": text} if text is not None else {},
        }
    elif type_message == "extendedTextMessage":
        message_data = {
            "typeMessage": "extendedTextMessage",
            "extendedTextMessageData": {"text": text} if text is not None else {},
        }
    else:
        message_data = {"typeMessage": type_message}

    return {
        "typeWebhook": type_webhook,
        "instanceData": {
            "idInstance": 7103000000,
            "wid": "972500000000@c.us",
            "typeInstance": "whatsapp",
        },
        "timestamp": 1588091580,
        "idMessage": id_message,
        "senderData": {
            "chatId": chat_id,
            "sender": chat_id,
            "senderName": "Customer",
        },
        "messageData": message_data,
    }


# ===========================================================================
# Schema parsing
# ===========================================================================


def test_schema_parses_text_message() -> None:
    payload = parse_webhook(_incoming_payload(text="12-345-67"))
    assert payload.is_incoming_message
    assert payload.text == "12-345-67"
    assert payload.chat_id == "972541234567@c.us"


def test_schema_parses_extended_text_message() -> None:
    payload = parse_webhook(
        _incoming_payload(text="Check 1234567", type_message="extendedTextMessage")
    )
    assert payload.text == "Check 1234567"


def test_schema_returns_none_text_for_non_text_message() -> None:
    payload = parse_webhook(_incoming_payload(text=None, type_message="imageMessage"))
    assert payload.text is None
    assert payload.is_incoming_message


def test_schema_accepts_unknown_webhook_type() -> None:
    payload = parse_webhook(
        _incoming_payload(type_webhook="outgoingMessageStatus")
    )
    assert not payload.is_incoming_message


def test_schema_ignores_extra_fields() -> None:
    raw = _incoming_payload()
    raw["unexpectedField"] = {"anything": True}
    raw["senderData"]["brandNewField"] = "ok"
    payload = parse_webhook(raw)
    assert payload.is_incoming_message


# ===========================================================================
# Service — pure business logic
# ===========================================================================


def _seed_vehicle(db_client: TestClient, status: VehicleStatus = VehicleStatus.mechanics) -> None:
    _create_vehicle(db_client, {"license_plate": _VALID_PLATE})
    # status defaults to ticket_opened; patch to requested status
    if status is not VehicleStatus.ticket_opened:
        r = db_client.patch(f"/vehicles/{_VALID_PLATE}", json={"status": status.value})
        assert r.status_code == 200, r.text


def _session():
    from tests.conftest import _TestSession  # type: ignore[attr-defined]

    return _TestSession()


def test_service_happy_path_returns_formatted_reply(client: TestClient) -> None:
    _seed_vehicle(client, VehicleStatus.mechanics)
    db = _session()
    try:
        result = handle_incoming_message("972541234567@c.us", "12-345-67", db)
    finally:
        db.close()
    assert result.reply is not None
    assert "Jane Doe" in result.reply
    assert _VALID_PLATE in result.reply
    assert STATUS_MESSAGES[VehicleStatus.mechanics] in result.reply


@pytest.mark.parametrize("status", list(VehicleStatus))
def test_service_covers_every_status(client: TestClient, status: VehicleStatus) -> None:
    _seed_vehicle(client, status)
    db = _session()
    try:
        result = handle_incoming_message("972541234567@c.us", _VALID_PLATE, db)
    finally:
        db.close()
    assert result.reply is not None
    assert STATUS_MESSAGES[status] in result.reply


def test_service_normalises_plate_from_mixed_separators(client: TestClient) -> None:
    _seed_vehicle(client)
    db = _session()
    try:
        result = handle_incoming_message(
            "972541234567@c.us", "plate: 12 345-67", db
        )
    finally:
        db.close()
    assert result.reply is not None
    assert _VALID_PLATE in result.reply


def test_service_accepts_eight_digit_plate(client: TestClient) -> None:
    _create_vehicle(client, {"license_plate": "12345678"})
    db = _session()
    try:
        result = handle_incoming_message("972541234567@c.us", "1234-5678", db)
    finally:
        db.close()
    assert result.reply is not None
    assert "12345678" in result.reply


@pytest.mark.parametrize(
    "text",
    ["", "   ", None],
)
def test_service_empty_text_returns_non_text_reply(text: str | None) -> None:
    db = _session()
    try:
        result = handle_incoming_message("972541234567@c.us", text, db)
    finally:
        db.close()
    assert result.reply == NON_TEXT_REPLY


@pytest.mark.parametrize(
    "text",
    ["abc", "12345", "123456789", "hello world", "plate: ABCDEFG"],
)
def test_service_invalid_plate_format(text: str) -> None:
    db = _session()
    try:
        result = handle_incoming_message("972541234567@c.us", text, db)
    finally:
        db.close()
    assert result.reply == INVALID_PLATE_REPLY


def test_service_plate_not_found() -> None:
    db = _session()
    try:
        result = handle_incoming_message("972541234567@c.us", "9999999", db)
    finally:
        db.close()
    assert result.reply == format_not_found("9999999")


def test_service_group_chat_returns_no_reply() -> None:
    db = _session()
    try:
        result = handle_incoming_message("123456789-987@g.us", "1234567", db)
    finally:
        db.close()
    assert result.reply is None
    assert result.skipped_reason == "group_chat"


def test_service_missing_chat_id_returns_no_reply() -> None:
    db = _session()
    try:
        result = handle_incoming_message(None, "1234567", db)
    finally:
        db.close()
    assert result.reply is None


# ===========================================================================
# Webhook endpoint — integration
# ===========================================================================


def test_webhook_happy_path_schedules_reply(
    client: TestClient, fake_client: _FakeClient
) -> None:
    _create_vehicle(client)
    r = client.post("/webhooks/whatsapp", json=_incoming_payload(text=_VALID_PLATE))
    assert r.status_code == 200
    assert len(fake_client.sent) == 1
    chat_id, message = fake_client.sent[0]
    assert chat_id == "972541234567@c.us"
    assert _VALID_PLATE in message
    assert "Jane Doe" in message


def test_webhook_normalises_plate_before_lookup(
    client: TestClient, fake_client: _FakeClient
) -> None:
    _create_vehicle(client, {"license_plate": _VALID_PLATE})
    r = client.post("/webhooks/whatsapp", json=_incoming_payload(text="12-345-67"))
    assert r.status_code == 200
    assert len(fake_client.sent) == 1
    assert _VALID_PLATE in fake_client.sent[0][1]


def test_webhook_plate_not_found_sends_not_found_copy(
    client: TestClient, fake_client: _FakeClient
) -> None:
    r = client.post("/webhooks/whatsapp", json=_incoming_payload(text="9999999"))
    assert r.status_code == 200
    assert len(fake_client.sent) == 1
    assert fake_client.sent[0][1] == format_not_found("9999999")


def test_webhook_invalid_plate_format_sends_invalid_copy(
    client: TestClient, fake_client: _FakeClient
) -> None:
    r = client.post("/webhooks/whatsapp", json=_incoming_payload(text="abc"))
    assert r.status_code == 200
    assert fake_client.sent == [("972541234567@c.us", INVALID_PLATE_REPLY)]


def test_webhook_non_text_message_sends_fallback(
    client: TestClient, fake_client: _FakeClient
) -> None:
    r = client.post(
        "/webhooks/whatsapp",
        json=_incoming_payload(text=None, type_message="imageMessage"),
    )
    assert r.status_code == 200
    assert fake_client.sent == [("972541234567@c.us", NON_TEXT_REPLY)]


def test_webhook_group_chat_is_ignored(
    client: TestClient, fake_client: _FakeClient
) -> None:
    r = client.post(
        "/webhooks/whatsapp",
        json=_incoming_payload(chat_id="123456789-987@g.us", text="1234567"),
    )
    assert r.status_code == 200
    assert fake_client.sent == []


def test_webhook_ignores_non_incoming_types(
    client: TestClient, fake_client: _FakeClient
) -> None:
    r = client.post(
        "/webhooks/whatsapp",
        json=_incoming_payload(type_webhook="outgoingMessageStatus"),
    )
    assert r.status_code == 200
    assert fake_client.sent == []


def test_webhook_deduplicates_repeated_id_message(
    client: TestClient, fake_client: _FakeClient
) -> None:
    _create_vehicle(client)
    body = _incoming_payload(text=_VALID_PLATE, id_message="DUP-1")
    assert client.post("/webhooks/whatsapp", json=body).status_code == 200
    assert client.post("/webhooks/whatsapp", json=body).status_code == 200
    assert len(fake_client.sent) == 1


def test_webhook_rejects_non_json_body(
    client: TestClient, fake_client: _FakeClient
) -> None:
    r = client.post(
        "/webhooks/whatsapp",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
    assert fake_client.sent == []


def test_webhook_rejects_non_object_body(
    client: TestClient, fake_client: _FakeClient
) -> None:
    r = client.post("/webhooks/whatsapp", json=["not", "an", "object"])
    assert r.status_code == 422
    assert fake_client.sent == []


def test_webhook_rejects_missing_type_webhook(
    client: TestClient, fake_client: _FakeClient
) -> None:
    r = client.post("/webhooks/whatsapp", json={"idMessage": "x"})
    assert r.status_code == 422
    assert fake_client.sent == []


def test_webhook_bearer_token_required_when_set(
    client: TestClient,
    fake_client: _FakeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.routers.whatsapp.settings.GREEN_API_WEBHOOK_TOKEN",
        "s3cret",
        raising=False,
    )
    _create_vehicle(client)

    r = client.post("/webhooks/whatsapp", json=_incoming_payload(text=_VALID_PLATE))
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == "Bearer"

    r = client.post(
        "/webhooks/whatsapp",
        json=_incoming_payload(text=_VALID_PLATE),
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401

    r = client.post(
        "/webhooks/whatsapp",
        json=_incoming_payload(text=_VALID_PLATE),
        headers={"Authorization": "Bearer s3cret"},
    )
    assert r.status_code == 200
    assert len(fake_client.sent) == 1


# ===========================================================================
# GreenApiClient — kill-switch + URL shape (no real HTTP)
# ===========================================================================


def test_client_noop_when_disabled() -> None:
    import asyncio

    c = GreenApiClient(
        base_url="https://example.invalid",
        id_instance="1",
        token_instance="t",
        enabled=False,
    )
    assert asyncio.run(c.send_message("972541234567@c.us", "hi")) is False


def test_client_requires_credentials_when_enabled() -> None:
    import asyncio

    c = GreenApiClient(
        base_url="https://example.invalid",
        id_instance="",
        token_instance="",
        enabled=True,
    )
    assert asyncio.run(c.send_message("972541234567@c.us", "hi")) is False


# ---------------------------------------------------------------------------
# Green-API JSON-level error handling (HTTP 200 but body says failure)
# ---------------------------------------------------------------------------


def _run_send_with_mock_transport(
    *, body: Any, http_status: int = 200, content_type: str = "application/json"
) -> bool:
    import asyncio

    import httpx

    def _handler(_request: httpx.Request) -> httpx.Response:
        if isinstance(body, (dict, list)):
            return httpx.Response(http_status, json=body)
        return httpx.Response(
            http_status, content=body, headers={"content-type": content_type}
        )

    transport = httpx.MockTransport(_handler)
    http_client = httpx.AsyncClient(transport=transport)
    c = GreenApiClient(
        base_url="https://example.invalid",
        id_instance="1",
        token_instance="t",
        enabled=True,
        http_client=http_client,
    )

    async def _run() -> bool:
        try:
            return await c.send_message("972541234567@c.us", "hi")
        finally:
            await http_client.aclose()

    return asyncio.run(_run())


def test_client_treats_idmessage_response_as_success() -> None:
    assert _run_send_with_mock_transport(body={"idMessage": "ABC"}) is True


def test_client_treats_non_200_body_status_code_as_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("ERROR", logger="app.whatsapp.client"):
        ok = _run_send_with_mock_transport(
            body={"statusCode": 466, "errorText": "Quota exceeded"}
        )
    assert ok is False
    assert any("reported failure in body" in rec.message for rec in caplog.records)


def test_client_treats_non_json_200_body_as_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("ERROR", logger="app.whatsapp.client"):
        ok = _run_send_with_mock_transport(
            body=b"<html>oops</html>", content_type="text/html"
        )
    assert ok is False
    assert any("non-JSON body" in rec.message for rec in caplog.records)


def test_client_treats_transport_error_as_failure() -> None:
    import asyncio

    import httpx

    def _handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated")

    transport = httpx.MockTransport(_handler)
    http_client = httpx.AsyncClient(transport=transport)
    c = GreenApiClient(
        base_url="https://example.invalid",
        id_instance="1",
        token_instance="t",
        enabled=True,
        http_client=http_client,
    )

    async def _run() -> bool:
        try:
            return await c.send_message("972541234567@c.us", "hi")
        finally:
            await http_client.aclose()

    assert asyncio.run(_run()) is False


# ---------------------------------------------------------------------------
# Phone-number mismatch canary
# ---------------------------------------------------------------------------


def test_service_logs_warning_on_phone_mismatch(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    _create_vehicle(client, {"phone_number": "0501234567"})
    db = _session()
    try:
        with caplog.at_level("WARNING", logger="app.whatsapp.service"):
            result = handle_incoming_message(
                "972987654321@c.us", _VALID_PLATE, db
            )
    finally:
        db.close()

    assert result.reply is not None  # reply is still produced
    mismatch_logs = [
        rec for rec in caplog.records if "Phone number mismatch" in rec.message
    ]
    assert len(mismatch_logs) == 1
    log_line = mismatch_logs[0].getMessage()
    assert _VALID_PLATE in log_line
    assert "972987654321@c.us" in log_line
    assert "0501234567" in log_line


def test_service_no_mismatch_log_when_numbers_match(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    _create_vehicle(client, {"phone_number": "0501234567"})
    db = _session()
    try:
        with caplog.at_level("WARNING", logger="app.whatsapp.service"):
            result = handle_incoming_message(
                "972501234567@c.us", _VALID_PLATE, db
            )
    finally:
        db.close()

    assert result.reply is not None
    assert not any(
        "Phone number mismatch" in rec.message for rec in caplog.records
    )


def test_formatting_fallback_for_unknown_status_is_generic() -> None:
    """Every known VehicleStatus must have a mapping; the generic fallback
    is only reached for unmapped future values."""
    for status_value in VehicleStatus:
        assert status_value in STATUS_MESSAGES


def test_format_vehicle_status_does_not_reference_estimated_completion(
    client: TestClient,
) -> None:
    _create_vehicle(client)
    from app.models.vehicle import Vehicle  # local import to avoid module-load-order issues

    db = _session()
    try:
        vehicle = db.get(Vehicle, _VALID_PLATE)
        assert vehicle is not None
        message = format_vehicle_status(vehicle)
    finally:
        db.close()
    assert "estimated" not in message.lower()
