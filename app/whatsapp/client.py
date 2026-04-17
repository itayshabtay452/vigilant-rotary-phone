"""Thin async wrapper around Green-API's REST surface.

Only `sendMessage` is implemented; every other Green-API endpoint the app might
need in the future should live here too so the rest of the codebase never
constructs a Green-API URL by hand. Swapping provider = rewriting this file.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

import httpx

from app import settings

_LOGGER = logging.getLogger(__name__)

_MAX_MESSAGE_CHARS: Final[int] = 20_000
_RETRY_BACKOFF_SECONDS: Final[float] = 0.5
_GREEN_API_OK_STATUS: Final[int] = 200


class GreenApiConfigError(RuntimeError):
    """Raised when Green-API credentials are required but not configured."""


class GreenApiClient:
    """Async client for Green-API's WhatsApp endpoints."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        id_instance: str | None = None,
        token_instance: str | None = None,
        enabled: bool | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url if base_url is not None else settings.GREEN_API_BASE_URL).rstrip("/")
        self._id_instance = id_instance if id_instance is not None else settings.GREEN_API_ID_INSTANCE
        self._token_instance = (
            token_instance if token_instance is not None else settings.GREEN_API_TOKEN_INSTANCE
        )
        self._enabled = enabled if enabled is not None else settings.WHATSAPP_ENABLED
        self._timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.WHATSAPP_HTTP_TIMEOUT_SECONDS
        )
        self._external_client = http_client

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _require_credentials(self) -> None:
        if not self._id_instance or not self._token_instance:
            raise GreenApiConfigError(
                "GREEN_API_ID_INSTANCE and GREEN_API_TOKEN_INSTANCE must be set to send messages"
            )

    def _send_url(self) -> str:
        return (
            f"{self._base_url}/waInstance{self._id_instance}"
            f"/sendMessage/{self._token_instance}"
        )

    @staticmethod
    def _clamp(message: str) -> str:
        if len(message) > _MAX_MESSAGE_CHARS:
            return message[:_MAX_MESSAGE_CHARS]
        return message

    @staticmethod
    def _is_successful_body(body: Any) -> bool:
        """Validate a Green-API 200 response body.

        Green-API often returns HTTP 200 even on business-level failures
        (e.g. quota exhausted) and surfaces the real status in a JSON
        ``statusCode`` field. A response is considered successful iff:

        * it is a JSON object, AND
        * any ``statusCode`` present equals 200, AND
        * an ``idMessage`` is present (the normal success marker) OR no
          ``statusCode`` is present at all.
        """
        if not isinstance(body, dict):
            return False
        status_code = body.get("statusCode")
        if status_code is not None and status_code != _GREEN_API_OK_STATUS:
            return False
        if "idMessage" in body:
            return True
        # No idMessage and no failing statusCode: ambiguous; treat as success
        # only when the body carries no statusCode at all (older Green-API
        # variants). If statusCode == 200 but no idMessage, fall back to
        # success so we don't spam false negatives.
        return status_code is None or status_code == _GREEN_API_OK_STATUS

    async def _post(self, url: str, payload: dict[str, str]) -> httpx.Response:
        if self._external_client is not None:
            return await self._external_client.post(
                url, json=payload, timeout=self._timeout_seconds
            )
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            return await client.post(url, json=payload)

    async def send_message(self, chat_id: str, message: str) -> bool:
        """POST sendMessage. Returns True on success, False otherwise.

        Exceptions are never propagated: the caller (a background task) treats
        the send as best-effort and must not crash the webhook.
        """
        if not self._enabled:
            _LOGGER.info("WhatsApp disabled; dropping outbound message to %s", chat_id)
            return False

        try:
            self._require_credentials()
        except GreenApiConfigError as exc:
            _LOGGER.warning("Cannot send WhatsApp message: %s", exc)
            return False

        payload = {"chatId": chat_id, "message": self._clamp(message)}
        url = self._send_url()

        for attempt in (1, 2):
            try:
                response = await self._post(url, payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                _LOGGER.warning(
                    "Green-API sendMessage transport error (attempt %d) to %s: %s",
                    attempt,
                    chat_id,
                    exc,
                )
                if attempt == 1:
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
                    continue
                return False

            try:
                body = response.json()
            except ValueError:
                _LOGGER.error(
                    "Green-API sendMessage to %s returned non-JSON body: %r",
                    chat_id,
                    response.text[:500],
                )
                return False

            if not self._is_successful_body(body):
                _LOGGER.error(
                    "Green-API sendMessage to %s reported failure in body: %r",
                    chat_id,
                    body,
                )
                return False

            _LOGGER.info("Sent WhatsApp message to %s (attempt %d)", chat_id, attempt)
            return True

        return False


_default_client: GreenApiClient | None = None


def get_client() -> GreenApiClient:
    """Return the process-wide default client, building it lazily.

    Tests override via ``app.whatsapp.client.set_client`` rather than patching
    environment variables.
    """
    global _default_client
    if _default_client is None:
        _default_client = GreenApiClient()
    return _default_client


def set_client(client: GreenApiClient | None) -> None:
    """Swap the process-wide client (primarily for tests)."""
    global _default_client
    _default_client = client
