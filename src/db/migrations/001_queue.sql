-- Inbound message queue
CREATE TABLE IF NOT EXISTS inbound_messages (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    wa_message_id   TEXT        NOT NULL UNIQUE,   -- WhatsApp dedup key
    phone_number    TEXT        NOT NULL,
    user_id         TEXT        NOT NULL,
    message_text    TEXT        NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Queue state machine: pending → claimed → done | failed
    status          TEXT        NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','claimed','done','failed')),
    claimed_at      TIMESTAMPTZ,
    worker_id       TEXT,                           -- which worker instance owns it
    done_at         TIMESTAMPTZ,
    retry_count     INT         NOT NULL DEFAULT 0,
    last_error      TEXT
);

CREATE INDEX IF NOT EXISTS idx_inbound_messages_status
    ON inbound_messages (status, received_at);

CREATE INDEX IF NOT EXISTS idx_inbound_messages_phone
    ON inbound_messages (phone_number, received_at);

-- NOTIFY worker pool whenever a new row lands
CREATE OR REPLACE FUNCTION notify_inbound_message()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('inbound_message', NEW.id::TEXT);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_inbound_message ON inbound_messages;
CREATE TRIGGER trg_notify_inbound_message
    AFTER INSERT ON inbound_messages
    FOR EACH ROW EXECUTE FUNCTION notify_inbound_message();
