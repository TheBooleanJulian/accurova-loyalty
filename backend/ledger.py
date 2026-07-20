"""
Ledger operations. All point movements go through add_entry() so the
idempotency guarantee is never bypassed.
"""
import secrets
import string
from database import get_conn

POINTS_PER_DOLLAR = 1          # tune: how many points per $1 spent on a booking
REFERRAL_BONUS = 100           # flat points to referrer when their referral completes 1st booking


def generate_referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "JUL-" + "".join(secrets.choice(alphabet) for _ in range(5))


def get_or_create_client(phone: str = None, email: str = None,
                          name: str = None, telegram_id: int = None,
                          referred_by_code: str = None):
    with get_conn() as conn:
        row = None
        if telegram_id:
            row = conn.execute("SELECT * FROM clients WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if not row and phone:
            row = conn.execute("SELECT * FROM clients WHERE phone = ?", (phone,)).fetchone()
        if not row and email:
            row = conn.execute("SELECT * FROM clients WHERE email = ?", (email,)).fetchone()
        if row:
            return row

        referred_by_id = None
        if referred_by_code:
            ref = conn.execute(
                "SELECT id FROM clients WHERE referral_code = ?", (referred_by_code,)
            ).fetchone()
            if ref:
                referred_by_id = ref["id"]

        code = generate_referral_code()
        cur = conn.execute(
            """INSERT INTO clients (name, phone, email, telegram_id, referral_code, referred_by_client_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, phone, email, telegram_id, code, referred_by_id),
        )
        return conn.execute("SELECT * FROM clients WHERE id = ?", (cur.lastrowid,)).fetchone()


def add_entry(client_id: int, delta: int, reason: str, reference_id: str = None,
              idempotency_key: str = None, note: str = None, created_by: str = "system") -> bool:
    """Returns True if the entry was written, False if it was a duplicate (idempotency hit)."""
    with get_conn() as conn:
        try:
            conn.execute(
                """INSERT INTO ledger (client_id, delta, reason, reference_id, idempotency_key, note, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (client_id, delta, reason, reference_id, idempotency_key, note, created_by),
            )
            return True
        except Exception as e:
            if "UNIQUE constraint failed: ledger.idempotency_key" in str(e):
                return False  # already processed this exact event — safe no-op
            raise


def get_balance(client_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(delta), 0) AS balance FROM ledger WHERE client_id = ?",
            (client_id,),
        ).fetchone()
        return row["balance"]


def get_history(client_id: int, limit: int = 20):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM ledger WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
            (client_id, limit),
        ).fetchall()


def record_booking_completed(client_phone_or_email: str, invoice_id: str, amount_sgd: float,
                              contact_type: str = "phone"):
    """Call this from InvoiceForge when an invoice is marked paid."""
    with get_conn() as conn:
        col = "phone" if contact_type == "phone" else "email"
        client = conn.execute(f"SELECT * FROM clients WHERE {col} = ?", (client_phone_or_email,)).fetchone()
    if not client:
        return None

    points = int(amount_sgd * POINTS_PER_DOLLAR)
    key = f"booking:{invoice_id}"
    written = add_entry(client["id"], points, "booking", reference_id=invoice_id,
                         idempotency_key=key, note=f"${amount_sgd:.2f} shoot")

    # First completed booking after being referred -> credit the referrer once.
    if written and client["referred_by_client_id"]:
        ref_key = f"referral_bonus:{client['id']}"  # one bonus per referred client, ever
        add_entry(client["referred_by_client_id"], REFERRAL_BONUS, "referral_bonus",
                  reference_id=str(client["id"]), idempotency_key=ref_key,
                  note=f"Referred client completed first booking")

    return points
