"""Send a fake signed WhatsApp webhook payload to the local server."""
import hashlib
import hmac
import json
import sys
import httpx
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Load .env so we can read META_APP_SECRET
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = os.getenv("NGROK_URL", "http://localhost:8000")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
PHONE = os.getenv("ALLOWED_PHONE_NUMBERS", "+14085551234").split(",")[0].strip()


def make_payload(phone: str, text: str, msg_id: str = "wamid.test123") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ENTRY_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": phone,
                                    "id": msg_id,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def sign(payload_bytes: bytes) -> str:
    sig = hmac.new(META_APP_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def main() -> None:
    text = " ".join(sys.argv[1:]) or "Hello from test script!"
    payload = make_payload(PHONE, text)
    body = json.dumps(payload).encode()
    signature = sign(body)

    print(f"POST {BASE_URL}/webhook")
    print(f"Phone : {PHONE}")
    print(f"Text  : {text}")

    resp = httpx.post(
        f"{BASE_URL}/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    print(f"Status: {resp.status_code}")
    print(f"Body  : {resp.text}")


if __name__ == "__main__":
    main()
