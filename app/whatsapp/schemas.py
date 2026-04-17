"""Pydantic models for Green-API webhook payloads.

Only the fields we actually consume are modelled; everything else on the wire
is ignored via `extra="ignore"` so Green-API can evolve their payload without
breaking us. The two text-bearing message shapes (`textMessage` and
`extendedTextMessage`) are normalised into a single `text` attribute on the
top-level model.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


_IncomingWebhookType = Literal["incomingMessageReceived"]


class _LooseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TextMessageData(_LooseModel):
    textMessage: str | None = None


class ExtendedTextMessageData(_LooseModel):
    text: str | None = None


class MessageData(_LooseModel):
    typeMessage: str
    textMessageData: TextMessageData | None = None
    extendedTextMessageData: ExtendedTextMessageData | None = None


class SenderData(_LooseModel):
    chatId: str
    sender: str | None = None
    senderName: str | None = None


class InstanceData(_LooseModel):
    idInstance: int | str | None = None
    wid: str | None = None
    typeInstance: str | None = None


class GreenApiWebhook(_LooseModel):
    """Root payload from Green-API.

    We accept any `typeWebhook` so the router can 200 OK non-incoming events
    (status updates, outgoing echoes, ...) without raising 422.
    """

    typeWebhook: str
    idMessage: str | None = None
    timestamp: int | None = None
    instanceData: InstanceData | None = None
    senderData: SenderData | None = None
    messageData: MessageData | None = None

    text: str | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _extract_text(self) -> "GreenApiWebhook":
        md = self.messageData
        if md is None:
            return self
        if md.typeMessage == "textMessage" and md.textMessageData is not None:
            self.text = md.textMessageData.textMessage
        elif md.typeMessage == "extendedTextMessage" and md.extendedTextMessageData is not None:
            self.text = md.extendedTextMessageData.text
        else:
            self.text = None
        return self

    @property
    def is_incoming_message(self) -> bool:
        return self.typeWebhook == "incomingMessageReceived"

    @property
    def chat_id(self) -> str | None:
        return self.senderData.chatId if self.senderData else None

    @property
    def sender_name(self) -> str | None:
        return self.senderData.senderName if self.senderData else None


def parse_webhook(payload: dict[str, Any]) -> GreenApiWebhook:
    """Validate and normalise a raw webhook body."""
    return GreenApiWebhook.model_validate(payload)
