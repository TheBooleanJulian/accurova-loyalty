"""
Accurova Loyalty API.

Run: uvicorn main:app --reload
Env vars: LOYALTY_SECRET, LOYALTY_ADMIN_KEY, SMTP_HOST/PORT/USER/PASS (optional)
"""
import os
import re

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import ledger
from database import init_db, get_conn

app = FastAPI(title="Accurova Loyalty API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ADMIN_KEY = os.environ.get("LOYALTY_ADMIN_KEY", "change-me-in-production")


@app.on_event("startup")
def startup():
    init_db()


def _is_email(contact: str) -> bool:
    return "@" in contact


# ---------- Web portal auth ----------

class OtpRequest(BaseModel):
    contact: str  # phone or email


@app.post("/api/otp/request")
def request_otp(body: OtpRequest):
    contact = body.contact.strip()
    with get_conn() as conn:
        col = "email" if _is_email(contact) else "phone"
        client = conn.execute(f"SELECT * FROM clients WHERE {col} = ?", (contact,)).fetchone()

    code = auth.request_otp(contact)

    # Prefer Telegram delivery if this client already has the bot linked.
    if client and client["telegram_id"]:
        # Hand off to the bot process to actually send it — see telegram_bot/bot.py send_otp()
        # For a single-process deploy you could import and call the bot's send fn directly instead.
        print(f"[telegram delivery] send {code} to telegram_id={client['telegram_id']}")
    elif _is_email(contact):
        auth.send_otp_email(contact, code)
    else:
        # No telegram link and no email — nothing to send to. In production, prompt the
        # client to also provide an email on first visit.
        raise HTTPException(400, "No delivery method on file for this contact. Try your email instead.")

    return {"status": "sent"}


class OtpVerify(BaseModel):
    contact: str
    code: str
    name: str | None = None
    referral_code: str | None = None  # only used if this is a brand-new client


@app.post("/api/otp/verify")
def verify_otp(body: OtpVerify):
    if not auth.verify_otp(body.contact, body.code):
        raise HTTPException(400, "Invalid or expired code")

    kwargs = {"name": body.name, "referred_by_code": body.referral_code}
    if _is_email(body.contact):
        kwargs["email"] = body.contact
    else:
        kwargs["phone"] = body.contact

    client = ledger.get_or_create_client(**kwargs)
    token = auth.issue_session_token(client["id"])
    return {"token": token}


def _require_client(authorization: str = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing session token")
    client_id = auth.verify_session_token(authorization.removeprefix("Bearer "))
    if not client_id:
        raise HTTPException(401, "Invalid or expired session")
    return client_id


@app.get("/api/me")
def me(authorization: str = Header(None)):
    client_id = _require_client(authorization)
    with get_conn() as conn:
        client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    balance = ledger.get_balance(client_id)
    history = [dict(row) for row in ledger.get_history(client_id)]
    return {
        "name": client["name"],
        "referral_code": client["referral_code"],
        "balance": balance,
        "history": history,
    }


# ---------- Admin / integration endpoints (called by InvoiceForge, or you manually) ----------

class BookingCompleted(BaseModel):
    contact: str
    invoice_id: str
    amount_sgd: float


@app.post("/api/admin/booking-completed")
def booking_completed(body: BookingCompleted, x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(403, "Invalid admin key")
    contact_type = "email" if _is_email(body.contact) else "phone"
    points = ledger.record_booking_completed(body.contact, body.invoice_id, body.amount_sgd, contact_type)
    if points is None:
        raise HTTPException(404, "No client found for that contact — create them first via signup")
    return {"points_awarded": points}


class Adjustment(BaseModel):
    client_id: int
    delta: int
    note: str


@app.post("/api/admin/adjust")
def adjust(body: Adjustment, x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(403, "Invalid admin key")
    ledger.add_entry(body.client_id, body.delta, "adjustment", note=body.note, created_by="admin")
    return {"status": "ok", "new_balance": ledger.get_balance(body.client_id)}


# Serve the web portal
app.mount("/", StaticFiles(directory="../web", html=True), name="web")
