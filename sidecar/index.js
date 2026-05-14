import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} from '@whiskeysockets/baileys'
import { Boom } from '@hapi/boom'
import express from 'express'
import pg from 'pg'
import pino from 'pino'
import 'dotenv/config'

const { Pool } = pg

const pool = new Pool({ connectionString: process.env.DATABASE_URL })

const ALLOWED = new Set(
  (process.env.ALLOWED_PHONE_NUMBERS || '').split(',').map(p => p.trim())
)

const logger = pino({ level: 'warn' })   // set to 'debug' for verbose Baileys logs

// ─── HTTP server — Python responder calls POST /send to reply ─────────────────

const app = express()
app.use(express.json())

let sock = null

app.post('/send', async (req, res) => {
  try {
    const { to, text } = req.body
    if (!sock) return res.status(503).json({ error: 'WhatsApp not connected yet' })

    const jid = `${to.replace(/^\+/, '')}@s.whatsapp.net`
    // WhatsApp hard-caps messages at 4096 chars
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

  sock = makeWASocket({
    version,
    auth: state,
    logger,
    printQRInTerminal: true,   // QR code prints here on first run
  })

  sock.ev.on('creds.update', saveCreds)

  sock.ev.on('connection.update', ({ connection, lastDisconnect }) => {
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
    // 'notify' = new messages pushed in real time; 'append' = history load
    if (type !== 'notify') return

    for (const msg of messages) {
      if (msg.key.fromMe) continue                                      // skip sent
      if (!msg.key.remoteJid?.endsWith('@s.whatsapp.net')) continue     // skip groups

      const text =
        msg.message?.conversation ??
        msg.message?.extendedTextMessage?.text ??
        ''
      if (!text.trim()) continue

      const rawPhone = msg.key.remoteJid.replace('@s.whatsapp.net', '')
      const phone = `+${rawPhone}`

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
