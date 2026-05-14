# Raw SQL schema lives in db/migrations/001_queue.sql.
# This module will hold any Python-level helpers for the inbound_messages table
# (e.g. dataclasses / named-tuple row types) once the worker is fleshed out.

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class InboundMessage:
    id: UUID
    wa_message_id: str
    phone_number: str
    user_id: str
    message_text: str
    received_at: datetime
    status: str          # pending | claimed | done | failed
    retry_count: int
