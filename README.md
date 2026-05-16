# AI Assistant

A personal WhatsApp-based AI assistant. Send a message to yourself on WhatsApp and get an AI-powered reply — no Meta Business account needed. Runs fully locally using Ollama.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR WHATSAPP                            │
└────────────────────────────┬────────────────────────────────────┘
                             │  WebSocket (Baileys)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BAILEYS SIDECAR  (Node.js)                    │
│  • QR auth — links as a device, no Meta Business account        │
│  • Filters by ALLOWED_PHONE_NUMBERS allowlist                   │
│  • Writes inbound messages → PostgreSQL queue                   │
│  • POST /send — sends replies back to WhatsApp                  │
└────────────────────────────┬────────────────────────────────────┘
                             │  INSERT + NOTIFY
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              POSTGRESQL  (queue + vector memory)                │
│                                                                 │
│  inbound_messages               mem0_memories                   │
│  ┌──────────────────────┐       ┌──────────────────────────┐   │
│  │ id · status          │       │ id · payload             │   │
│  │ phone_number         │       │ vector(768)  [HNSW idx]  │   │
│  │ message_text         │       └──────────────────────────┘   │
│  │ reply_jid            │                                       │
│  │ LISTEN/NOTIFY trigger│       pgvector extension              │
│  └──────────────────────┘                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │  LISTEN/NOTIFY → claim (SKIP LOCKED)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PYTHON WORKER  (asyncio)                      │
│  • 8s debounce per phone — coalesces burst messages             │
│  • FOR UPDATE SKIP LOCKED — safe multi-worker claiming          │
│  • Reaper — resets stuck messages every 60s                     │
└────────────────────────────┬────────────────────────────────────┘
                             │  graph.ainvoke()
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH AGENT                              │
│                                                                 │
│   context_loader                                                │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Mem0.search(query, user_id)                            │  │
│   │  nomic-embed-text (Ollama) → pgvector cosine search     │  │
│   │  injects top-5 memories into state                      │  │
│   └─────────────────────────┬───────────────────────────────┘  │
│                             ▼                                   │
│   research_expert                                               │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  qwen2.5:7b (Ollama)                                    │  │
│   │  system prompt includes top-5 memories from Mem0        │  │
│   │  → generates reply_text                                 │  │
│   └─────────────────────────┬───────────────────────────────┘  │
│                             ▼                                   │
│   memory_writer                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Mem0.add(turn, user_id, infer=False)                   │  │
│   │  nomic-embed-text → pgvector INSERT                     │  │
│   └─────────────────────────┬───────────────────────────────┘  │
│                             ▼                                   │
│   responder                                                     │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  send_whatsapp_message(phone, reply, reply_jid)         │  │
│   │  POST /send → Baileys sidecar → WhatsApp                │  │
│   └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Stack**
- **Sidecar** — Node.js + [@whiskeysockets/baileys](https://github.com/WhiskeySockets/Baileys). Connects to WhatsApp as a linked device (QR scan, no Meta app needed), writes inbound messages to Postgres, exposes `POST /send` for replies.
- **Queue** — PostgreSQL `inbound_messages` table with `LISTEN/NOTIFY` trigger and `FOR UPDATE SKIP LOCKED` worker claiming.
- **Worker** — Python asyncio. Listens on Postgres channel, 8-second debounce per phone to coalesce burst messages, claims and processes rows, invokes LangGraph agent.
- **Agent** — LangGraph graph: `context_loader → research_expert → memory_writer → responder`.
- **Memory** — [Mem0](https://mem0.ai) with pgvector. Semantic search over past conversations, stored in the same Postgres DB.
- **LLM** — `qwen2.5:7b` via Ollama (local, no API key). Swap to any Ollama model or OpenAI-compatible endpoint.
- **Embeddings** — `nomic-embed-text` via Ollama (local, 768-dim).

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
    nodes.py        # context_loader, research_expert, memory_writer, responder
    graph.py        # Graph builder (MemorySaver checkpointer)
    mem0_client.py  # Mem0 Memory singleton (pgvector + Ollama)
  tools/
    search.py       # Tavily web search tool (wired in slice 3)
  db/
    connection.py   # asyncpg pool
    migrations/
      001_queue.sql
      002_add_reply_jid.sql

scripts/
  setup_db.py       # Run all SQL migrations
  test_webhook.py   # Insert a fake message into the queue for testing
  test_mem0.py      # Test Mem0 store + search in isolation
  test_graph.py     # Run full LangGraph graph end-to-end (no WhatsApp needed)
```

## Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL with pgvector extension (recommended: [Postgres.app](https://postgresapp.com) on Mac)
- [Ollama](https://ollama.com) with `qwen2.5:7b` and `nomic-embed-text` pulled

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

### 2. Pull Ollama models

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

### 3. Configure

```bash
cp .env.example .env
# Required: ALLOWED_PHONE_NUMBERS, DATABASE_URL
```

### 4. Database

```bash
createdb assistant
source .venv/bin/activate
python scripts/setup_db.py
```

### 5. Run

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

### 6. Test

Send yourself a message in WhatsApp ("Message Yourself" chat) — you'll get an AI reply.

Test the graph without WhatsApp:
```bash
python scripts/test_graph.py
```

Test Mem0 memory in isolation:
```bash
python scripts/test_mem0.py
```

Inject a test message directly into the queue:
```bash
python scripts/test_webhook.py "hello world"
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ALLOWED_PHONE_NUMBERS` | ✅ | Comma-separated E.164 numbers allowed to use the assistant |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `SIDECAR_URL` | — | Baileys sidecar URL (default: `http://localhost:3000`) |
| `ANTHROPIC_API_KEY` | slice 3 | Anthropic API key (cloud LLM fallback) |
| `TAVILY_API_KEY` | slice 3 | Tavily search API key (research_expert web search) |

## Notes

- Baileys is an **unofficial** WhatsApp library. Use at your own risk — keep message volume low.
- `sidecar/auth/` stores your WhatsApp session. Keep it private and never commit it.
- The `ALLOWED_PHONE_NUMBERS` allowlist ensures only your number (and anyone you explicitly add) can interact with the assistant.
- Mem0 memory is stored in the `mem0_memories` table in your PostgreSQL DB — auto-created on first run.
- To change the LLM, update `LM_STUDIO_MODEL` / `base_url` in `src/graph/nodes.py`. Any Ollama model or OpenAI-compatible endpoint works.
