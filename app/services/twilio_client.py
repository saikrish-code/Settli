"""Twilio WhatsApp client — sends outbound messages via the Twilio REST API.

Used by split_bill to notify participants and by the main webhook
to reply to the user.
"""

from __future__ import annotations

import logging

from twilio.rest import Client  # type: ignore[import-untyped]

from app.config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def _get_client() -> Client:
    """Lazy-initialize the Twilio client."""
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


async def send_whatsapp_message(to: str, body: str) -> str:
    """Send a WhatsApp message via Twilio.

    Args:
        to: Recipient phone number (E.164 format, e.g. "+919876543210").
            Will be prefixed with "whatsapp:" if not already.
        body: Message body text.

    Returns:
        The Twilio message SID of the sent message.
    """
    if not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"

    client = _get_client()

    try:
        message = client.messages.create(
            body=body,
            from_=settings.twilio_whatsapp_number,
            to=to,
        )
        logger.info("Sent WhatsApp message: sid=%s, to=%s", message.sid, to)
        return str(message.sid)

    except Exception:
        logger.exception("Failed to send WhatsApp message to %s", to)
        raise
