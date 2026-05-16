# TODO

## ✅ Done (v0 slice 1)

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

## 🔨 In Progress (v0 slice 2)

- [ ] LangGraph graph wiring
  - [ ] `context_loader` — pull last N messages from PostgresSaver checkpointer
  - [ ] `supervisor` — intent classification, route to expert
  - [ ] `research_expert` — LLM + Tavily web search tool
  - [ ] `memory_writer` — persist turn to DB
  - [ ] `responder` — format and send reply

## 📋 Backlog

- [ ] Replace echo stub in `worker._generate_reply()` with LangGraph graph call
- [ ] PostgresSaver checkpointer — conversation memory across sessions
- [ ] Semantic memory / RAG (slice 3)
- [ ] Multi-expert routing in supervisor (slice 3)
- [ ] Image / voice message handling
- [ ] Aditi and other contacts in allowlist
- [ ] Admin CLI — list pending messages, force reprocess, clear queue
- [ ] Deployment — single-machine Docker Compose (sidecar + worker + postgres)
- [ ] Monitoring — Prometheus metrics on queue depth, processing latency
