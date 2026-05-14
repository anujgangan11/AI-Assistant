import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} from '@whiskeysockets/baileys'
import { Boom } from '@hapi/boom'
import express from 'express'
import pg from 'pg'
import pino from 'pino'
import qrcode from 'qrcode-terminal'
import dotenv from 'dotenv'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: join(__dirname, '../.env') })

const { Pool } = pg

const pool = new Pool({ connectionString: process.env.DATABASE_URL })

const ALLOWED = new Set(
  (process.env.ALLOWED_PHONE_NUMBERS || '').split(',').map(p => p.trim())
)

const logger = pino({ level: 'warn' })

// @lid → E.164 phone number, populated from contacts sync on startup
const lidToPhone = new Map()

// ─── HTTP server — Python responder calls POST /send to reply ─────────────────

const app = express()
app.use(express.json())

let sock = null

app.post('/send', async (req, res) => {
  try {
    const { to, text } = req.body
    if (!sock) return res.status(503).json({ error: 'WhatsApp not connected yet' })

    const jid = `${to.replace(/^\+/, '')}@s.whatsapp.net`
    const chunks = text.match(/.{1,4096}/gs) ?? [text]
    for (const chunk of chunks) {
      await sock.sendMessage(jid, { text: chunk })
    }
    res.json({ status: 'ok' })
  } catch (err) {
    console.error('Send error:', err.message)
    res.status(500).json({ error: err.message })
  }
})

app.get('/health', (_req, res) =>
  res.json({ status: 'ok', connected: sock !== null })
)

app.listen(3000, () => console.log('Sidecar HTTP listening on :3000'))

// ─── WhatsApp connection via Baileys ─────────────────────────────────────────

async function connect() {
  const { version } = await fetchLatestBaileysVersion()
  const { state, saveCreds } = await useMultiFileAuthState('./auth')

  sock = makeWASocket({ version, auth: state, logger })

  sock.ev.on('creds.update', saveCreds)

  // Build @lid → phone map from contacts sync
  sock.ev.on('contacts.upsert', (contacts) => {
    for (const c of contacts) {
      if (c.lid && c.id?.endsWith('@s.whatsapp.net')) {
        const phone = `+${c.id.replace('@s.whatsapp.net', '')}`
        lidToPhone.set(c.lid, phone)
      }
    }
  })

  sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      console.log('\nScan this QR code with WhatsApp → Settings → Linked Devices → Link a Device:\n')
      qrcode.generate(qr, { small: true })
    }
    if (connection === 'open') {
      console.log('Connected to WhatsApp')
    } else if (connection === 'close') {
      sock = null
      const code = new Boom(lastDisconnect?.error)?.output?.statusCode
      if (code === DisconnectReason.loggedOut) {
        console.log('Logged out — delete ./auth/ and restart to re-scan QR')
      } else {
        console.log(`Connection closed (code ${code}) — reconnecting…`)
        connect()
      }
    }
  })

  // ─── Inbound messages ───────────────────────────────────────────────────────

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return

    for (const msg of messages) {
      const jid = msg.key.remoteJid ?? ''

      const text =
        msg.message?.conversation ??
        msg.message?.extendedTextMessage?.text ??
        ''
      if (!text.trim()) continue

      let phone

      if (jid.endsWith('@s.whatsapp.net')) {
        // Standard JID — phone number is in the JID
        phone = `+${jid.replace('@s.whatsapp.net', '')}`
      } else if (jid.endsWith('@lid')) {
        if (msg.key.fromMe) {
          // Self-chat ("Message Yourself")
          phone = [...ALLOWED][0]
        } else {
          // Contact using privacy ID — resolve via contacts map
          phone = lidToPhone.get(jid) ?? null
          if (!phone) {
            console.log(`Cannot resolve @lid ${jid} — skipping (contact not yet synced)`)
            continue
          }
        }
      } else {
        continue  // group or unknown JID type
      }

      if (!ALLOWED.has(phone)) {
        console.log(`Ignored message from non-allowlisted number: ${phone}`)
        continue
      }

      try {
        await pool.query(
          `INSERT INTO inbound_messages (wa_message_id, phone_number, user_id, message_text)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (wa_message_id) DO NOTHING`,
          [msg.key.id, phone, phone, text]
        )
        console.log(`Queued from ${phone}: ${text.slice(0, 80)}`)
      } catch (err) {
        console.error('DB insert error:', err.message)
      }
    }
  })
}

connect()
