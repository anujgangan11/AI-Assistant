# AI Assistant

A personal WhatsApp-based AI assistant. Send a message to yourself on WhatsApp and get an AI-powered reply — no Meta Business account needed.

## Architecture

```
WhatsApp ←──WebSocket──→ Baileys Sidecar (Node.js)
                                │
                         PostgreSQL queue
                                │
                         Python Worker
                                │
                    LangGraph Agent (coming soon)
                                │
                         Reply via sidecar
```

**Stack**
- **Sidecar** — Node.js + [@whiskeysockets/baileys](https://github.com/WhiskeySockets/Baileys). Connects to WhatsApp as a linked device (QR scan, no Meta app needed), writes inbound messages to Postgres, exposes `POST /send` for replies.
- **Queue** — PostgreSQL `inbound_messages` table with `LISTEN/NOTIFY` trigger and `FOR UPDATE SKIP LOCKED` worker claiming.
- **Worker** — Python asyncio. Listens on Postgres channel, 8-second debounce per phone to coalesce burst messages, claims and processes rows, sends reply via sidecar.
- **Agent** — LangGraph supervisor graph (in progress): `context_loader → supervisor → research_expert → memory_writer → responder`.

## Project Structure

```
sidecar/
  index.js          # Baileys WhatsApp connection + HTTP /send endpoint
  package.json

src/
  main.py           # FastAPI app (health check)
  config.py         # Env var settings
  gateway/
    whatsapp.py     # send_whatsapp_message() — calls sidecar
  queue/
    worker.py       # LISTEN/NOTIFY loop, debounce, SKIP LOCKED claim
    reaper.py       # Reset stuck messages every 60s
    models.py       # Row dataclass
  graph/
    state.py        # LangGraph TypedDict state
    nodes.py        # Node functions (stubs)
    graph.py        # Graph builder
  tools/
    search.py       # Tavily web search tool
  db/
    connection.py   # asyncpg pool
    migrations/
      001_queue.sql
      002_add_reply_jid.sql

scripts/
  setup_db.py       # Run all SQL migrations
  test_webhook.py   # Insert a fake message into the queue for testing
```

## Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL (recommended: [Postgres.app](https://postgresapp.com) on Mac)

### 1. Clone & install

```bash
git clone https://github.com/anujgangan11/AI-Assistant.git
cd AI-Assistant

# Python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Node (sidecar)
cd sidecar && npm install && cd ..
```

### 2. Configure

```bash
cp .env.example .env
# Fill in: ALLOWED_PHONE_NUMBERS, ANTHROPIC_API_KEY, TAVILY_API_KEY, DATABASE_URL
```

### 3. Database

```bash
createdb assistant
source .venv/bin/activate
python scripts/setup_db.py
```

### 4. Run

**Terminal 1 — WhatsApp sidecar:**
```bash
cd sidecar && node index.js
# Scan the QR code with WhatsApp → Settings → Linked Devices → Link a Device
```

**Terminal 2 — Worker:**
```bash
source .venv/bin/activate
python -m src.queue.worker
```

### 5. Test

Send yourself a message in WhatsApp ("Message Yourself" chat) — you'll get an echo reply in 8 seconds.

Or inject a test message directly:
```bash
python scripts/test_webhook.py "hello world"
```

## Environment Variables

| Variable | Description |
|---|---|
| `ALLOWED_PHONE_NUMBERS` | Comma-separated E.164 numbers allowed to use the assistant |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `TAVILY_API_KEY` | Tavily search API key |
| `DATABASE_URL` | PostgreSQL connection string |
| `SIDECAR_URL` | Baileys sidecar URL (default: `http://localhost:3000`) |

## Notes

- Baileys is an **unofficial** WhatsApp library. Use at your own risk — keep message volume low.
- `sidecar/auth/` stores your WhatsApp session. Keep it private and never commit it.
- The `ALLOWED_PHONE_NUMBERS` allowlist ensures only your number (and anyone you explicitly add) can interact with the assistant.
