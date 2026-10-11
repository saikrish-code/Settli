"""All SQL queries as module-level constants.

Keeping SQL in one place makes it auditable and easy to review.
No query logic is scattered across tool functions.
"""

# ── Schema Creation (for testing / fresh installs) ─────────────

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           TEXT UNIQUE NOT NULL,
    name            TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    phone           TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(owner_id, name)
);

CREATE TABLE IF NOT EXISTS expenses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    amount          NUMERIC(12,2) NOT NULL,
    category        TEXT NOT NULL DEFAULT 'general',
    description     TEXT,
    split_with      TEXT[],
    split_amounts   NUMERIC(12,2)[],
    message_sid     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS budgets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    category        TEXT NOT NULL DEFAULT 'overall',
    monthly_limit   NUMERIC(12,2) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, category)
);

CREATE TABLE IF NOT EXISTS reminders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    message         TEXT NOT NULL,
    remind_at       TIMESTAMPTZ NOT NULL,
    is_sent         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    message_sid     TEXT,
    tool_name       TEXT NOT NULL,
    tool_input      JSONB NOT NULL,
    tool_output     JSONB,
    status          TEXT NOT NULL DEFAULT 'success',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS processed_messages (
    message_sid     TEXT PRIMARY KEY,
    response_body   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
"""

# ── Users ──────────────────────────────────────────────────────

UPSERT_USER = """
INSERT INTO users (phone, name)
VALUES ($1, $2)
ON CONFLICT (phone) DO UPDATE SET name = COALESCE(EXCLUDED.name, users.name)
RETURNING id, phone, name, created_at;
"""

GET_USER_BY_PHONE = """
SELECT id, phone, name, created_at FROM users WHERE phone = $1;
"""

# ── Contacts ───────────────────────────────────────────────────

UPSERT_CONTACT = """
INSERT INTO contacts (owner_id, name, phone)
VALUES ($1, $2, $3)
ON CONFLICT (owner_id, name) DO UPDATE SET phone = EXCLUDED.phone
RETURNING id, owner_id, name, phone, created_at;
"""

GET_CONTACTS_BY_OWNER = """
SELECT id, owner_id, name, phone, created_at
FROM contacts
WHERE owner_id = $1
ORDER BY name;
"""

GET_CONTACT_BY_NAME = """
SELECT id, owner_id, name, phone, created_at
FROM contacts
WHERE owner_id = $1 AND LOWER(name) = LOWER($2);
"""

# ── Expenses ───────────────────────────────────────────────────

INSERT_EXPENSE = """
INSERT INTO expenses (user_id, amount, category, description, split_with, split_amounts, message_sid)
VALUES ($1, $2, $3, $4, $5, $6, $7)
RETURNING id, user_id, amount, category, description, split_with, split_amounts, message_sid, created_at;
"""

GET_EXPENSES_BY_PERIOD = """
SELECT id, user_id, amount, category, description, split_with, split_amounts, message_sid, created_at
FROM expenses
WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
ORDER BY created_at DESC;
"""

GET_CATEGORY_TOTALS_BY_PERIOD = """
SELECT category, SUM(amount) as total
FROM expenses
WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
GROUP BY category
ORDER BY total DESC;
"""

GET_TOTAL_BY_PERIOD = """
SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
FROM expenses
WHERE user_id = $1 AND created_at >= $2 AND created_at < $3;
"""

GET_CATEGORY_TOTAL_THIS_MONTH = """
SELECT COALESCE(SUM(amount), 0) as total
FROM expenses
WHERE user_id = $1
  AND category = $2
  AND created_at >= date_trunc('month', now())
  AND created_at < date_trunc('month', now()) + interval '1 month';
"""

# ── Budgets ────────────────────────────────────────────────────

UPSERT_BUDGET = """
INSERT INTO budgets (user_id, category, monthly_limit)
VALUES ($1, $2, $3)
ON CONFLICT (user_id, category) DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit
RETURNING id, user_id, category, monthly_limit, created_at;
"""

GET_BUDGET = """
SELECT id, user_id, category, monthly_limit, created_at
FROM budgets
WHERE user_id = $1 AND category = $2;
"""

# ── Reminders ──────────────────────────────────────────────────

INSERT_REMINDER = """
INSERT INTO reminders (user_id, message, remind_at)
VALUES ($1, $2, $3)
RETURNING id, user_id, message, remind_at, is_sent, created_at;
"""

GET_PENDING_REMINDERS = """
SELECT id, user_id, message, remind_at, is_sent, created_at
FROM reminders
WHERE is_sent = FALSE AND remind_at <= now()
ORDER BY remind_at;
"""

MARK_REMINDER_SENT = """
UPDATE reminders SET is_sent = TRUE WHERE id = $1;
"""

# ── Audit Log ──────────────────────────────────────────────────

INSERT_AUDIT_LOG = """
INSERT INTO audit_log (user_id, message_sid, tool_name, tool_input, tool_output, status)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING id, user_id, message_sid, tool_name, tool_input, tool_output, status, created_at;
"""

# ── Idempotency ────────────────────────────────────────────────

INSERT_PROCESSED_MESSAGE = """
INSERT INTO processed_messages (message_sid, response_body)
VALUES ($1, $2)
ON CONFLICT (message_sid) DO NOTHING;
"""

GET_PROCESSED_MESSAGE = """
SELECT message_sid, response_body, created_at
FROM processed_messages
WHERE message_sid = $1;
"""
