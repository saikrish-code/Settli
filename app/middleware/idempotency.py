"""Idempotency guard — prevents duplicate processing of Twilio retries.

Twilio retries webhook POSTs on 5xx or timeout (up to 3 times). Without
dedupe, one user message could log three expenses.

Mechanism:
  1. Check if MessageSid exists in processed_messages
  2. If yes → return the cached response (no re-processing)
  3. If no  → process the message, cache the response
"""

from __future__ import annotations

import logging

from app.db import operations as db

logger = logging.getLogger(__name__)


async def check_idempotency(message_sid: str) -> str | None:
    """Check if a message has already been processed.

    Args:
        message_sid: The Twilio MessageSid.

    Returns:
        The cached response body if this is a duplicate, None if it's new.
    """
    existing = await db.get_processed_message(message_sid)
    if existing is not None:
        logger.info("Duplicate message detected: %s, returning cached response", message_sid)
        return existing["response_body"]
    return None


async def mark_processed(message_sid: str, response_body: str) -> None:
    """Record a message as processed with its response.

    Args:
        message_sid: The Twilio MessageSid.
        response_body: The TwiML response to cache for retries.
    """
    await db.try_insert_processed_message(message_sid, response_body)
    logger.debug("Marked message as processed: %s", message_sid)
