# Settli - Implementation Plan

## Project Overview

Settli is a WhatsApp-native agentic expense tracker and bill-splitting assistant built with:
- **Python 3.11+** with FastAPI
- **asyncpg** (raw SQL, no ORM)
- **PostgreSQL** database
- **Twilio WhatsApp API** for messaging
- **LLM tool-calling agent** with provider-agnostic JSON-mode parser
- **LocalMockProvider** for deterministic tests
- **pytest** for testing

## Architecture Summary

### 7-Table Schema
1. **users** - User accounts (phone, name)
2. **contacts** - User's contacts for bill splitting
3. **expenses** - Expense records with category, amount, split info
4. **budgets** - Monthly spending limits per category
5. **reminders** - Scheduled reminders
6. **audit_log** - Every tool call logged for auditability
7. **processed_messages** - Idempotency deduplication (Twilio MessageSid)

### LLM Guardrail Strategy

The agent output is constrained to a **discriminated union**:

```python
AgentResponse = ToolCall | ClarificationRequest
```

- **ToolCall**: Must name one of 5 valid tools with validated args
- **ClarificationRequest**: Ask user for missing/ambiguous information
- **Fallback**: Any invalid output becomes a clarification request

### Idempotency Approach

Twilio retries webhook POSTs on 5xx/timeout (up to 3 times). Without dedupe:
- Same user message → 3 duplicate expenses

Solution: `processed_messages` table with `message_sid` as primary key:
1. Check if MessageSid exists → return cached response
2. If new → process, cache response, return

## 6-Phase Delivery Plan

### Phase 1: Core Infrastructure ✅
- [x] Project setup (pyproject.toml, dependencies)
- [x] Config management (pydantic-settings)
- [x] Database pool lifecycle
- [x] SQL queries module
- [x] Pydantic models for all entities

### Phase 2: Database Layer ✅
- [x] 7-table schema (users, contacts, expenses, budgets, reminders, audit_log, processed_messages)
- [x] CRUD operations for all entities
- [x] Audit logging infrastructure
- [x] Idempotency operations

### Phase 3: Agent Layer ✅
- [x] System prompt with tool schemas
- [x] JSON-mode parser with discriminated union
- [x] Provider protocol (OpenAI, Groq, LocalMock)
- [x] LocalMockProvider for CI testing

### Phase 4: Tools ✅
- [x] log_expense - Record expenses with budget checking
- [x] split_bill - Notify participants via WhatsApp
- [x] get_summary - Period summaries with category breakdown
- [x] set_reminder - Schedule reminders
- [x] set_budget - Monthly limits per category
- [x] split_math - Penny-perfect Decimal arithmetic

### Phase 5: Tests ✅
- [x] test_parser.py - LLM parser (ToolCall vs ClarificationRequest)
- [x] test_split_math.py - Penny-perfect split verification
- [x] test_tools.py - All 5 tools in isolation
- [x] test_idempotency.py - Idempotency concept
- [x] test_audit.py - Audit logging pattern
- [x] test_db_operations.py - Database operation patterns
- [x] conftest.py with mock fixtures

### Phase 6: Production Readiness
- [ ] GitHub Actions CI pipeline
- [ ] README.md with setup instructions
- [ ] Live Twilio Sandbox verification
- [ ] Optional: Celery Beat proactive "Budget Guardian" job

## Interview Talking Points

1. **Guardrails over guardrails**: The discriminated union ensures the LLM can't escape valid outputs
2. **Penny-perfect splitting**: Decimal arithmetic, not float - sum(shares) == total, always
3. **Provider-agnostic design**: Swap OpenAI/Groq/Mock without code changes
4. **Audit-first architecture**: Every tool call logged for compliance
5. **Idempotency by design**: Twilio retries don't create duplicates
6. **Asyncpg over ORM**: Raw SQL for control, transparency, auditability
7. **Contact management**: Pre-agent regex routing for CRUD commands
8. **Budget warnings**: 80% threshold alerts, over-budget notifications
9. **WhatsApp-native**: Real-time notifications to split participants
10. **Testability**: LocalMockProvider enables deterministic CI tests
11. **Multi-step agent behavior**: One message triggers lookup → calculate → notify
12. **Graceful degradation**: Tool failures → clarification, not crashes

## Environment Variables

```bash
# Twilio
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# LLM Provider (openai, groq, or mock)
LLM_PROVIDER=mock
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o-mini
GROQ_API_KEY=gsk_xxx
GROQ_MODEL=llama-3.3-70b-versatile

# Database
DATABASE_URL=postgresql://settli:settli@localhost:5432/settli

# App
LOG_LEVEL=INFO
APP_ENV=development
```

## Running the Project

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linter
ruff check app/

# Start server
uvicorn app.main:app --reload
```

## Next Steps

1. Set up PostgreSQL database locally
2. Run schema creation (app/db/queries.py CREATE_TABLES)
3. Configure Twilio Sandbox credentials
4. Test end-to-end with ngrok
5. Set up CI pipeline
