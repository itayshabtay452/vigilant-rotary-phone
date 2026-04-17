"""Inbound WhatsApp webhook router (Green-API flavour).

Design notes:

- Returns 200 on every authenticated call so Green-API never retries messages
  we've already accepted. Anything we can't act on (wrong webhook type, group
  chat, non-text) is acknowledged silently.
- Auth is a dedicated Bearer-token check against `GREEN_API_WEBHOOK_TOKEN`
  (constant-time). When the env var is empty we fall back to open access so
  local dev and CI don't need to wire a secret — matching the `ADMIN_API_KEY`
  convention in `app.dependencies`.
- Duplicate deliveries are short-circuited via a bounded LRU keyed by
  `idMessage`.
- The outbound reply is scheduled via `BackgroundTasks` so the HTTP 200
  returns before Green-API's `sendMessage` round-trip.
"""
from __future__ import annotations

import hmac
import logging
from collections import OrderedDict
from typing import Any, Final

_HTTP_422: Final[int] = 422

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import settings
from app.database import get_db
from app.whatsapp.client import GreenApiClient, get_client
from app.whatsapp.schemas import GreenApiWebhook, parse_webhook
from app.whatsapp.service import handle_incoming_message

_LOGGER = logging.getLogger(__name__)

_DEDUPE_MAX_ENTRIES: Final[int] = 1000
_BEARER_PREFIX: Final[str] = "Bearer "


class _LRUSet:
    """Order-preserving bounded set used to dedupe `idMessage` values."""

    __slots__ = ("_items", "_max")

    def __init__(self, max_entries: int) -> None:
        self._items: "OrderedDict[str, None]" = OrderedDict()
        self._max = max_entries

    def __contains__(self, key: str) -> bool:
        return key in self._items

    def add(self, key: str) -> None:
        if key in self._items:
            self._items.move_to_end(key)
            return
        self._items[key] = None
        while len(self._items) > self._max:
            self._items.popitem(last=False)


_seen_messages = _LRUSet(_DEDUPE_MAX_ENTRIES)


def _reset_dedupe_cache_for_tests() -> None:
    """Clear the module-level LRU. Exposed for tests; not part of the API."""
    global _seen_messages
    _seen_messages = _LRUSet(_DEDUPE_MAX_ENTRIES)


def verify_green_api_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    expected = settings.GREEN_API_WEBHOOK_TOKEN
    if not expected:
        return

    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        _LOGGER.warning("WhatsApp webhook rejected: missing or malformed Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided = authorization[len(_BEARER_PREFIX):].strip()
    if not hmac.compare_digest(provided, expected):
        _LOGGER.warning("WhatsApp webhook rejected: invalid bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


router = APIRouter(prefix="/webhooks", tags=["whatsapp"])


async def _dispatch_reply(client: GreenApiClient, chat_id: str, message: str) -> None:
    """Background-task entrypoint: swallows every error."""
    try:
        await client.send_message(chat_id, message)
    except Exception:  # noqa: BLE001  — best-effort, never crash the background runner
        _LOGGER.exception("Unexpected error sending WhatsApp reply to %s", chat_id)


def _parse_body(raw: Any) -> GreenApiWebhook:
    try:
        return parse_webhook(raw)
    except ValidationError as exc:
        _LOGGER.warning("WhatsApp webhook payload failed validation: %s", exc)
        raise HTTPException(
            status_code=_HTTP_422,
            detail="Invalid webhook payload",
        ) from exc


@router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_green_api_token),
) -> Response:
    try:
        raw = await request.json()
    except ValueError as exc:
        _LOGGER.warning("WhatsApp webhook received non-JSON body: %s", exc)
        raise HTTPException(
            status_code=_HTTP_422,
            detail="Invalid JSON body",
        ) from exc

    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=_HTTP_422,
            detail="Webhook body must be a JSON object",
        )

    payload = _parse_body(raw)

    if not payload.is_incoming_message:
        return Response(status_code=status.HTTP_200_OK)

    if payload.idMessage is not None:
        if payload.idMessage in _seen_messages:
            _LOGGER.info("Duplicate WhatsApp idMessage=%s ignored", payload.idMessage)
            return Response(status_code=status.HTTP_200_OK)
        _seen_messages.add(payload.idMessage)

    result = handle_incoming_message(payload.chat_id, payload.text, db)

    if result.reply is None:
        if result.skipped_reason:
            _LOGGER.info("Skipping reply: %s", result.skipped_reason)
        return Response(status_code=status.HTTP_200_OK)

    chat_id = payload.chat_id
    assert chat_id is not None  # reply only set when chat_id present

    # CRITICAL: The reply string MUST be fully materialized before scheduling
    # this task. Do not pass DB sessions or ORM objects here to avoid
    # DetachedInstanceError — the request-scoped Session from `get_db` is
    # closed as soon as this handler returns, so any lazy-loaded attribute
    # access on a Vehicle would fail once the background task actually runs.
    background_tasks.add_task(_dispatch_reply, get_client(), chat_id, result.reply)
    return Response(status_code=status.HTTP_200_OK)
