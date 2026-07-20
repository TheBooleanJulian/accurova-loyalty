"""
OTP-based login for the web portal. No passwords to manage or leak.

Delivery: if the client has a linked telegram_id, send the code via the bot
(reuses infra you already have). Otherwise fall back to email. This is what
makes the portal usable for clients who don't use Telegram — the whole point
of this file.

Session tokens are short-lived signed tokens (HMAC), not JWT libs — simple,
no extra dependency, easy to reason about.
"""
import hashlib
import hmac
import os
import random
import smtplib
import time
from email.mime.text import MIMEText

from database import get_conn

SECRET = os.environ.get("LOYALTY_SECRET", "change-me-in-production")
OTP_TTL_SECONDS = 5 * 60
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days — low-stakes data, long session is fine

# Set these in your deploy env (Zeabur) if using email OTP fallback.
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")


def _gen_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def request_otp(contact: str) -> str:
    """Creates and 'sends' an OTP. Returns the code (caller decides delivery channel)."""
    code = _gen_code()
    expires_at = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + OTP_TTL_SECONDS))
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO otp_codes (contact, code, expires_at) VALUES (?, ?, ?)",
            (contact, code, expires_at),
        )
    return code


def send_otp_email(to_email: str, code: str):
    if not SMTP_HOST:
        print(f"[dev mode] OTP for {to_email}: {code}")  # no SMTP configured — log instead
        return
    msg = MIMEText(f"Your Accurova loyalty portal code is {code}. It expires in 5 minutes.")
    msg["Subject"] = "Your Accurova loyalty code"
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def verify_otp(contact: str, code: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM otp_codes WHERE contact = ? AND code = ? AND used = 0
               ORDER BY created_at DESC LIMIT 1""",
            (contact, code),
        ).fetchone()
        if not row:
            return False
        if time.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S") < time.gmtime():
            return False
        conn.execute("UPDATE otp_codes SET used = 1 WHERE id = ?", (row["id"],))
        return True


def issue_session_token(client_id: int) -> str:
    expiry = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{client_id}.{expiry}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session_token(token: str):
    try:
        client_id, expiry, sig = token.split(".")
        payload = f"{client_id}.{expiry}"
        expected_sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        if int(expiry) < time.time():
            return None
        return int(client_id)
    except (ValueError, AttributeError):
        return None
