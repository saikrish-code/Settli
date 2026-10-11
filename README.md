# Settli 💰

**WhatsApp-native agentic expense tracker and bill-splitting assistant**

Settli is an intelligent expense management bot that lives in WhatsApp. Send a message like *"spent 250 on chai with Raj and Priya, split 3 ways"* and Settli will:
1. Log the ₹250 expense
2. Calculate each person's share (₹83.34, ₹83.33, ₹83.33)
3. Send WhatsApp notifications to Raj and Priya with their amounts
4. Check your budget and warn you if needed

All from a single natural language message.

## Features

- 🤖 **LLM-powered agent** with constrained output (no hallucinations)
- 💸 **Smart bill splitting** with penny-perfect arithmetic
- 📊 **Expense tracking** with categories and summaries
- 💰 **Budget alerts** at 80% and 100% thresholds
- ⏰ **Reminders** for upcoming payments
- 📝 **Contact management** for easy splitting
- 🔒 **Idempotent** — Twilio retries don't create duplicates
- 📋 **Audit log** — Every action logged for compliance

## Architecture

```
WhatsApp → Twilio → FastAPI Webhook → LLM Agent → Tools → PostgreSQL
                                    ↓
                              [ToolCall | Clarification]
```

**Key Design Decisions:**

1. **Discriminated Union Guardrails**: LLM output constrained to `ToolCall | ClarificationRequest`
2. **Asyncpg + Raw SQL**: No ORM for auditability and control
3. **Penny-Perfect Splitting**: Decimal arithmetic, `sum(shares) == total` always
4. **Provider-Agnostic**: Swap OpenAI/Groq/Mock via env var
5. **LocalMockProvider**: Regex-based testing without API costs

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 13+
- Twilio account with WhatsApp sandbox

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/settli.git
cd settli

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your Twilio credentials and database URL

# 4. Set up database
createdb settli
psql -d settli -c "$(cat app/db/queries.py | grep -A 200 'CREATE_TABLES')"

# 5. Run tests
pytest tests/ -v

# 6. Start the server
uvicorn app.main:app --reload
```

### Local Development with Twilio

```bash
# 1. Start ngrok
ngrok http 8000

# 2. Configure Twilio webhook
# Go to Twilio Console → WhatsApp Sandbox Settings
# Set "When a message comes in" to: https://your-ngrok-url.ngrok.io/webhook

# 3. Join sandbox
# Send "join <your-sandbox-code>" to your Twilio WhatsApp number

# 4. Test it!
# Send: "spent 250 on chai"
# Bot responds: "✅ Logged ₹250 for chai (food)"
```

## Usage Examples

### Log an Expense
```
You: spent 150 on uber
Bot: ✅ Logged ₹150 for uber (transport)
```

### Split a Bill
```
You: spent 900 on dinner with Raj and Priya, split 3 ways
Bot: 💰 Split ₹900 (3 ways):
     • You: ₹300 (you)
     • Raj: ₹300 (✅ notified)
     • Priya: ₹300 (✅ notified)
```

### Get Summary
```
You: how much did I spend this month?
Bot: 📊 Spending summary for this month:
     💰 Total: ₹4250 (12 expenses)
     
     By category:
       • food: ₹1800
       • transport: ₹950
       • entertainment: ₹1500
```

### Set Budget
```
You: set my food budget to 3000
Bot: ✅ Budget set!
     📂 Category: food
     💰 Monthly limit: ₹3000
```

### Set Reminder
```
You: remind me to pay rent on the 5th
Bot: ⏰ Reminder set!
     📝 Pay Rent
     🗓️ November 05, 2026 at 09:00 AM
```

### Manage Contacts
```
You: add contact Raj +919876543210
Bot: ✅ Contact saved: Raj (+919876543210)

You: contacts
Bot: 📇 Your contacts:
       • Raj: +919876543210
       • Priya: +919876543211
```

## Tools

Settli has 5 tools the LLM agent can call:

| Tool | Purpose | Example |
|------|---------|---------|
| `log_expense` | Record an expense | "spent 250 on chai" |
| `split_bill` | Split and notify participants | "split 900 with Raj and Priya" |
| `get_summary` | View spending breakdown | "how much this month?" |
| `set_budget` | Set monthly limits | "set food budget to 3000" |
| `set_reminder` | Schedule reminders | "remind me to pay rent on 5th" |

## Database Schema

7 tables for complete expense tracking:

- **users** — User accounts (phone, name)
- **contacts** — User's contacts for bill splitting
- **expenses** — Expense records with category, amount, split info
- **budgets** — Monthly spending limits per category
- **reminders** — Scheduled reminders
- **audit_log** — Every tool call logged
- **processed_messages** — Idempotency deduplication

## Configuration

All configuration via environment variables:

```bash
# Required
DATABASE_URL=postgresql://user:pass@localhost:5432/settli
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Optional
LLM_PROVIDER=mock          # mock | openai | groq
OPENAI_API_KEY=sk-xxxxx    # if LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
GROQ_API_KEY=gsk_xxxxx     # if LLM_PROVIDER=groq
GROQ_MODEL=llama-3.3-70b-versatile
LOG_LEVEL=INFO
APP_ENV=development
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_parser.py -v
pytest tests/test_split_math.py -v
pytest tests/test_tools.py -v

# Run with coverage (requires pytest-cov)
pytest tests/ --cov=app --cov-report=term-missing
```

**Test Coverage:**
- ✅ LLM parser (valid/invalid outputs, fallback behavior)
- ✅ Split math (penny-perfect invariant verification)
- ✅ All 5 tools (success paths + edge cases)
- ✅ Idempotency (deduplication logic)
- ✅ Audit logging (every action logged)

**34 tests, all passing**

## Development

### Code Quality

```bash
# Linting
ruff check app/

# Apply safe fixes
ruff check app/ --fix

# Type checking
mypy app/
```

### Project Structure

```
Settli/
├── app/
│   ├── main.py              # FastAPI app, webhook handler
│   ├── config.py            # Pydantic settings
│   ├── agent/               # LLM providers & parser
│   ├── db/                  # Database layer (asyncpg)
│   ├── tools/               # 5 tools + registry
│   ├── models/              # Pydantic models
│   ├── services/            # Twilio client, audit
│   └── middleware/          # Idempotency
├── tests/                   # Test suite (34 tests)
├── .github/workflows/       # CI pipeline
└── pyproject.toml           # Project config
```

## How It Works

### 1. Message Arrives
User sends WhatsApp message → Twilio webhook → POST to `/webhook`

### 2. Idempotency Check
Check `processed_messages` table by MessageSid:
- Already processed? Return cached response
- New message? Continue processing

### 3. LLM Classification
Send message to LLM with tool schemas → Parse output:
- `ToolCall` with valid tool name + args → Execute tool
- `ClarificationRequest` → Ask user for missing info
- Invalid output → Fallback to clarification

### 4. Tool Execution
Dispatch to tool function:
- Validate input via Pydantic
- Execute database operations
- Check budgets, send notifications
- Return structured output

### 5. Audit & Response
- Log to `audit_log` table (tool name, input, output, status)
- Build TwiML response
- Cache in `processed_messages`
- Return to Twilio → User gets WhatsApp reply

## The "Penny-Perfect" Guarantee

Settli uses `Decimal` arithmetic (not float) to ensure:

```python
calculate_split(Decimal("250"), 3)
# → [Decimal('83.34'), Decimal('83.33'), Decimal('83.33')]

# Invariant: sum(shares) == total (always)
assert sum([83.34, 83.33, 83.33]) == 250  # True!
```

Remainder pennies are distributed to the first people in the split. No rounding errors, ever.

## LLM Providers

Settli supports 3 LLM providers:

| Provider | Use Case | Setup |
|----------|----------|-------|
| **LocalMockProvider** | Testing, CI | No API key needed |
| **OpenAIProvider** | Production (gpt-4o-mini) | Set `OPENAI_API_KEY` |
| **GroqProvider** | Production (llama-3.3-70b) | Set `GROQ_API_KEY` |

Switch via `LLM_PROVIDER` env var. All use the same JSON-mode parser.

## Deployment

### Railway / Render

```bash
# Set environment variables in platform dashboard
DATABASE_URL=postgresql://...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Deploy
# Platform will run: pip install -e . && uvicorn app.main:app
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t settli .
docker run -p 8000:8000 --env-file .env settli
```

## Roadmap

- [x] Core expense tracking
- [x] Bill splitting with notifications
- [x] Budget alerts
- [x] Contact management
- [x] Reminders
- [x] Audit logging
- [x] Test suite (34 tests)
- [x] CI pipeline
- [ ] Celery Beat proactive budget checks
- [ ] Multi-currency support
- [ ] Recurring expenses
- [ ] Receipt OCR (photo uploads)
- [ ] Export to CSV/Excel
- [ ] Web dashboard

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Run the test suite (`pytest tests/ -v`)
5. Run linting (`ruff check app/`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Security

- Never commit `.env` files or secrets
- Twilio webhooks validate via signature (add validation middleware for production)
- Audit log captures all actions for compliance
- PostgreSQL row-level security recommended for multi-tenant deployments

## License

MIT License - see [LICENSE](LICENSE) for details

## Support

- 📧 Email: support@settli.example.com
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/settli/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/settli/discussions)

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) — Modern async web framework
- [asyncpg](https://github.com/MagicStack/asyncpg) — Fast PostgreSQL driver
- [Twilio](https://www.twilio.com/) — WhatsApp Business API
- [Pydantic](https://pydantic.dev/) — Data validation
- [OpenAI](https://openai.com/) / [Groq](https://groq.com/) — LLM providers

---

Made with ❤️ for splitting bills fairly
