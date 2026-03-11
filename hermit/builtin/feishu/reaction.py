"""Feishu message emoji reaction utilities.

Configuration (environment variables):
  HERMIT_FEISHU_REACTION_ENABLED   true/false  Master switch (default: true)
  HERMIT_FEISHU_REACTION_ACK       emoji name  Auto "thinking" reaction (default: EYES)
  HERMIT_FEISHU_REACTION_DONE      emoji name  Auto "done" reaction (default: empty = off)
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

# Friendly alias → Feishu emoji_type string.
# Full reference: https://open.larkoffice.com/document/server-docs/im-v1/message-reaction/emojis-introduce
EMOJI_ALIASES: dict[str, str] = {
    # Acknowledgement / thinking
    "eyes": "EYES",
    "thinking": "THINKING_FACE",
    "watching": "EYES",
    # Positive / success
    "thumbsup": "THUMBSUP",
    "ok": "OK",
    "done": "OK",
    "check": "OK",
    "fire": "FIRE",
    "clap": "CLAP",
    "congrats": "CONGRATULATIONS",
    "party": "CONGRATULATIONS",
    "hooray": "CONGRATULATIONS",
    "heart": "HEART",
    "love": "HEART",
    "smile": "SMILE",
    "happy": "SMILE",
    # Surprise / question
    "surprised": "SURPRISED",
    "wow": "SURPRISED",
    # Negative
    "thumbsdown": "THUMBSDOWN",
    "no": "THUMBSDOWN",
    "cry": "CRY",
    "sad": "CRY",
}


def resolve_emoji(name: str) -> str:
    """Resolve a friendly alias or raw Feishu emoji_type string."""
    lowered = name.strip().lower()
    return EMOJI_ALIASES.get(lowered, name.strip().upper().replace(" ", "_"))


def add_reaction(client: Any, message_id: str, emoji_type: str) -> bool:
    """Add an emoji reaction to a Feishu message. Returns True on success."""
    if not client or not message_id or not emoji_type:
        return False
    try:
        from lark_oapi.api.im.v1 import (
            CreateMessageReactionRequest,
            CreateMessageReactionRequestBody,
        )
        from lark_oapi.api.im.v1.model.emoji import Emoji

        emoji = Emoji.builder().emoji_type(emoji_type).build()
        body = CreateMessageReactionRequestBody.builder().reaction_type(emoji).build()
        request = (
            CreateMessageReactionRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )
        response = client.im.v1.message_reaction.create(request)
        if not response.success():
            log.debug(
                "reaction_failed msg=%s emoji=%s code=%s msg=%s",
                message_id,
                emoji_type,
                response.code,
                response.msg,
            )
            return False
        log.debug("reaction_ok msg=%s emoji=%s", message_id, emoji_type)
        return True
    except Exception as exc:
        log.debug("reaction_error msg=%s emoji=%s err=%s", message_id, emoji_type, exc)
        return False


def _is_enabled(settings: object | None = None) -> bool:
    raw = getattr(settings, "feishu_reaction_enabled", None)
    if raw is not None:
        return bool(raw)
    return os.environ.get("HERMIT_FEISHU_REACTION_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _ack_emoji(settings: object | None = None) -> str:
    raw = getattr(settings, "feishu_reaction_ack", None)
    if raw is not None:
        return str(raw)
    return os.environ.get("HERMIT_FEISHU_REACTION_ACK", "EYES")


def _done_emoji(settings: object | None = None) -> str:
    raw = getattr(settings, "feishu_reaction_done", None)
    if raw is not None:
        return str(raw)
    return os.environ.get("HERMIT_FEISHU_REACTION_DONE", "")


def send_ack(client: Any, message_id: str, settings: object | None = None) -> None:
    """Send 'received / working on it' reaction (configurable, default: 👀 EYES)."""
    if not _is_enabled(settings):
        return
    emoji = _ack_emoji(settings)
    if emoji:
        add_reaction(client, message_id, emoji)


def send_done(client: Any, message_id: str, settings: object | None = None) -> None:
    """Send 'reply done' reaction if configured (default: disabled)."""
    if not _is_enabled(settings):
        return
    emoji = _done_emoji(settings)
    if emoji:
        add_reaction(client, message_id, emoji)
