"""Pydantic model for the incoming Twilio WhatsApp webhook payload.

Twilio sends form-encoded POST requests. These are the fields we care about.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TwilioWebhookPayload(BaseModel):
    """Validates the form-encoded POST body from Twilio.

    We only extract the fields we need; Twilio sends many more.
    Using Field(alias=...) to map Twilio's PascalCase to our snake_case.
    """

    message_sid: str = Field(..., alias="MessageSid")
    account_sid: str = Field(..., alias="AccountSid")
    from_number: str = Field(..., alias="From")
    to_number: str = Field(..., alias="To")
    body: str = Field(..., alias="Body")
    num_media: str = Field(default="0", alias="NumMedia")

    model_config = {"populate_by_name": True}
