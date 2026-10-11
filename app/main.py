"""Settli — FastAPI application entry point.

This module wires everything together:
  - Lifespan: DB pool creation/teardown, tool registration
  - POST /webhook: Twilio incoming message handler
  - Contact management: pre-agent regex routing for CRUD commands
  - Agent orchestration: LLM classification → tool execution → audit → reply
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Form, Response
from pydantic import ValidationError

from app.agent.provider import get_provider
from app.config import settings
from app.db.pool import close_pool, create_pool
from app.middleware.idempotency import check_idempotency, mark_processed
from app.models.agent import ClarificationRequest, ToolCall
from app.models.webhook import TwilioWebhookPayload
from app.services.audit import log_tool_call
from app.tools.registry import UnknownToolError, execute_tool, register_all_tools

# ── Logging Setup ──────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("settli")


# ── Lifespan ───────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown logic."""
    logger.info("Starting Settli...")
    logger.info("LLM Provider: %s", settings.llm_provider.value)

    # Initialize DB pool
    await create_pool()

    # Register tools
    register_all_tools()

    logger.info("Settli started successfully ✓")
    yield

    # Shutdown
    logger.info("Shutting down Settli...")
    await close_pool()
    logger.info("Settli shut down ✓")


# ── FastAPI App ────────────────────────────────────────────────

app = FastAPI(
    title="Settli",
    description="WhatsApp-native agentic expense tracker & bill-splitting assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# LLM provider (initialized lazily)
_llm_provider = None


def _get_llm():
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = get_provider()
    return _llm_provider


# ── Health Check ───────────────────────────────────────────────


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "settli"}


# ── Contact Management (Pre-agent routing) ─────────────────────

ADD_CONTACT_RE = re.compile(
    r"^add\s+contact\s+(\w+)\s+(\+?\d{10,15})$", re.IGNORECASE
)
LIST_CONTACTS_RE = re.compile(r"^(?:my\s+)?contacts$", re.IGNORECASE)


async def _handle_contact_command(
    body: str, user_id: Any
) -> str | None:
    """Handle contact management commands. Returns reply text or None."""
    from app.db import operations as db

    # Add contact
    match = ADD_CONTACT_RE.match(body.strip())
    if match:
        name = match.group(1).strip().title()
        phone = match.group(2).strip()
        if not phone.startswith("+"):
            phone = f"+91{phone}"  # Default to India country code
        await db.upsert_contact(user_id, name, phone)
        return f"✅ Contact saved: {name} ({phone})"

    # List contacts
    if LIST_CONTACTS_RE.match(body.strip()):
        contacts = await db.get_contacts_by_owner(user_id)
        if not contacts:
            return "📇 No contacts saved yet. Add one with:\nadd contact <name> <phone>"
        lines = ["📇 Your contacts:"]
        for c in contacts:
            lines.append(f"  • {c['name']}: {c['phone']}")
        return "\n".join(lines)

    return None


# ── Webhook Endpoint ───────────────────────────────────────────


def _make_twiml_response(message: str) -> str:
    """Build a TwiML XML response string."""
    # Escape XML special characters
    escaped = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escaped}</Message></Response>"
    )


@app.post("/webhook")
async def webhook(
    MessageSid: str = Form(...),
    AccountSid: str = Form(...),
    From: str = Form(..., alias="From"),
    To: str = Form(...),
    Body: str = Form(...),
    NumMedia: str = Form(default="0"),
) -> Response:
    """Handle incoming WhatsApp messages from Twilio.

    This is the main entry point. Flow:
      1. Validate the payload
      2. Check idempotency (dedupe retries)
      3. Upsert user
      4. Check for contact management commands
      5. Run the LLM agent
      6. Execute tool calls
      7. Audit log everything
      8. Return TwiML response
    """
    from app.db import operations as db

    logger.info(
        "Webhook received: sid=%s, from=%s, body=%s",
        MessageSid,
        From,
        Body[:100],
    )

    try:
        # ── Step 1: Validate payload ──
        payload = TwilioWebhookPayload(
            MessageSid=MessageSid,
            AccountSid=AccountSid,
            From=From,
            To=To,
            Body=Body,
            NumMedia=NumMedia,
        )
    except ValidationError as e:
        logger.error("Invalid Twilio payload: %s", e)
        return Response(
            content=_make_twiml_response("Sorry, something went wrong."),
            media_type="application/xml",
            status_code=200,  # Always 200 to Twilio
        )

    try:
        # ── Step 2: Idempotency check ──
        cached = await check_idempotency(payload.message_sid)
        if cached is not None:
            logger.info("Returning cached response for %s", payload.message_sid)
            return Response(content=cached, media_type="application/xml")

        # ── Step 3: Upsert user ──
        user_row = await db.upsert_user(payload.from_number)
        user_id = user_row["id"]
        user_name = user_row["name"]

        # ── Step 4: Contact management (pre-agent) ──
        contact_reply = await _handle_contact_command(payload.body, user_id)
        if contact_reply is not None:
            twiml = _make_twiml_response(contact_reply)
            await mark_processed(payload.message_sid, twiml)
            return Response(content=twiml, media_type="application/xml")

        # ── Step 5: Run LLM agent ──
        llm = _get_llm()
        agent_responses = await llm.classify(payload.body)
        logger.info("Agent responses: %s", agent_responses)

        # ── Step 6: Process responses ──
        reply_parts: list[str] = []

        for response in agent_responses:
            if isinstance(response, ClarificationRequest):
                reply_parts.append(response.question)
                # Audit the clarification
                await log_tool_call(
                    user_id=user_id,
                    message_sid=payload.message_sid,
                    tool_name="clarification",
                    tool_input={"user_message": payload.body},
                    tool_output={"question": response.question},
                    status="clarification",
                )

            elif isinstance(response, ToolCall):
                try:
                    result = await execute_tool(
                        tool_call=response,
                        user_id=user_id,
                        message_sid=payload.message_sid,
                        user_phone=payload.from_number,
                        user_name=user_name,
                    )

                    # Audit successful tool call
                    result_dict = result.model_dump(mode="json") if hasattr(result, "model_dump") else {"result": str(result)}
                    await log_tool_call(
                        user_id=user_id,
                        message_sid=payload.message_sid,
                        tool_name=response.tool,
                        tool_input=response.args,
                        tool_output=result_dict,
                        status="success",
                    )

                    # Extract the human-readable message from the result
                    if hasattr(result, "message"):
                        reply_parts.append(result.message)
                    elif hasattr(result, "confirmation"):
                        reply_parts.append(result.confirmation)

                    # Check for budget warning
                    if hasattr(result, "budget_warning") and result.budget_warning:
                        reply_parts.append(result.budget_warning)

                    # If this was a log_expense with split_with, trigger split_bill
                    if (
                        response.tool == "log_expense"
                        and hasattr(result, "expense_id")
                        and response.args.get("split_with")
                    ):
                        split_result = await execute_tool(
                            tool_call=ToolCall(
                                tool="split_bill",
                                args={
                                    "expense_id": str(result.expense_id),
                                    "participants": response.args["split_with"],
                                    "total": float(result.amount),
                                },
                            ),
                            user_id=user_id,
                            message_sid=payload.message_sid,
                            user_phone=payload.from_number,
                            user_name=user_name,
                        )

                        # Audit the split
                        split_dict = split_result.model_dump(mode="json") if hasattr(split_result, "model_dump") else {}
                        await log_tool_call(
                            user_id=user_id,
                            message_sid=payload.message_sid,
                            tool_name="split_bill",
                            tool_input={
                                "expense_id": str(result.expense_id),
                                "participants": response.args["split_with"],
                                "total": float(result.amount),
                            },
                            tool_output=split_dict,
                            status="success",
                        )

                        if hasattr(split_result, "message"):
                            reply_parts.append(split_result.message)

                except UnknownToolError as e:
                    logger.error("Unknown tool: %s", e.tool_name)
                    reply_parts.append(
                        f"I tried to use a tool called '{e.tool_name}' but it doesn't exist. "
                        "Could you rephrase your request?"
                    )

                except ValidationError as e:
                    logger.warning("Tool validation error: %s", e)
                    # Extract the field names that failed
                    errors = e.errors()
                    missing_fields = [
                        err["loc"][-1] for err in errors if err["type"] == "missing"
                    ]
                    if missing_fields:
                        reply_parts.append(
                            f"I need more information: {', '.join(str(f) for f in missing_fields)}. "
                            "Could you provide those details?"
                        )
                    else:
                        reply_parts.append(
                            "Some of the details seem off. Could you rephrase?"
                        )
                    await log_tool_call(
                        user_id=user_id,
                        message_sid=payload.message_sid,
                        tool_name=response.tool,
                        tool_input=response.args,
                        tool_output={"errors": [str(err) for err in errors]},
                        status="error",
                    )

                except Exception as e:
                    logger.exception("Tool execution error: %s", e)
                    reply_parts.append("Something went wrong. Please try again.")
                    await log_tool_call(
                        user_id=user_id,
                        message_sid=payload.message_sid,
                        tool_name=response.tool,
                        tool_input=response.args,
                        tool_output={"error": str(e)},
                        status="error",
                    )

        # ── Step 7: Build reply ──
        if not reply_parts:
            reply_parts.append(
                "I'm not sure how to help with that. Could you try something like:\n"
                "• 'spent 200 on lunch'\n"
                "• 'how much did I spend this month?'\n"
                "• 'set my food budget to 3000'"
            )

        reply_text = "\n\n".join(reply_parts)

        # ── Step 8: Cache and return ──
        twiml = _make_twiml_response(reply_text)
        await mark_processed(payload.message_sid, twiml)

        return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.exception("Unhandled error in webhook: %s", e)
        twiml = _make_twiml_response(
            "😔 Something went wrong on our end. Please try again."
        )
        return Response(content=twiml, media_type="application/xml")
