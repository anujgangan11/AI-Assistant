# TODO

## ✅ Done (v0 slice 1) — Queue & Transport

- [x] Baileys sidecar — QR auth, WebSocket connection, auto-reconnect
- [x] Inbound message routing — `@s.whatsapp.net` and `@lid` JID handling
- [x] Allowlist filtering by phone number
- [x] Outgoing message guard — don't queue messages you send to others
- [x] PostgreSQL queue — `inbound_messages` table with LISTEN/NOTIFY trigger
- [x] `reply_jid` column — routes replies back to correct chat (incl. self-chat `@lid`)
- [x] Worker — LISTEN/NOTIFY loop, 8s debounce per phone, SKIP LOCKED claim
- [x] Reaper — resets stuck `claimed` messages every 60s
- [x] Echo stub reply — full round-trip working end to end
- [x] `scripts/test_webhook.py` — inject test messages without WhatsApp

## ✅ Done (v0 slice 2) — LangGraph Agent + Memory

- [x] LangGraph graph wired: `context_loader → research_expert → memory_writer → responder`
- [x] `context_loader` — Mem0 semantic search (nomic-embed-text + pgvector) injects top-5 memories
- [x] `research_expert` — qwen2.5:7b via Ollama, system prompt includes user memories
- [x] `memory_writer` — Mem0 stores each conversation turn in pgvector
- [x] `responder` — sends reply via Baileys sidecar with correct `reply_jid` routing
- [x] Worker `_generate_reply` stub replaced with `graph.ainvoke()`
- [x] Mem0 self-hosted — pgvector + nomic-embed-text + qwen2.5:7b (all local, no API key)
- [x] `scripts/test_mem0.py` — test Mem0 store + search in isolation
- [x] `scripts/test_graph.py` — test full graph end-to-end without WhatsApp

## 🔨 In Progress (v0 slice 3) — Reliability & Tools

- [x] End-to-end WhatsApp test — send real message, get real AI reply
- [x] Enable Mem0 `infer=True` once Ollama speeds are reliable (LLM fact extraction)
- [ ] PostgresSaver checkpointer — persistent conversation thread across worker restarts
- [ ] Tavily web search tool wired into `research_expert`
- [ ] Intent routing in supervisor — classify query type before dispatching

## 📋 Backlog

- [ ] Semantic memory / RAG improvements (explicit "remember that X" trigger)
- [ ] Multi-expert routing in supervisor (slice 3+)
- [ ] Image / voice message handling
- [ ] Additional contacts in allowlist (Aditi etc.)
- [ ] Admin CLI — list pending messages, force reprocess, clear queue
- [ ] Deployment — single-machine Docker Compose (sidecar + worker + postgres + ollama)
- [ ] Monitoring — Prometheus metrics on queue depth, processing latency
- [ ] Switch to AsyncPostgresSaver for durable conversation history
