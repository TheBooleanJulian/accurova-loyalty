# Accurova Loyalty Program

One points ledger, three access points: Telegram bot, web portal, QR codes.

## Architecture

```
loyalty-program/
  backend/
    database.py   — SQLite schema (WAL mode), clients + ledger + otp_codes tables
    ledger.py     — add_entry() / get_balance() / record_booking_completed()
    auth.py       — OTP generation + verification, session tokens
    main.py       — FastAPI app: web portal API + admin endpoints
    requirements.txt
  telegram_bot/
    bot.py        — /start /mystatus /refer, deep-link referral capture
  web/
    index.html    — client portal (no Telegram needed): phone/email -> OTP -> dashboard
```

## The two entry paths into the same ledger

**Telegram-first clients**: `/start` in the bot creates their client record instantly —
Telegram's own auth is the login, no OTP needed.

**Web-first clients (no Telegram)**: they enter phone or email on the portal, get a
6-digit OTP (via email, since they have no Telegram to send it to), verify, and get a
signed session token stored in their browser. Same `clients` table, same `ledger` table
— just a different front door. If they later also start the bot, `get_or_create_client`
matches them by phone/email so the accounts merge automatically rather than duplicating.

## Wiring up InvoiceForge

When an invoice is marked paid, call:

```
POST /api/admin/booking-completed
X-Admin-Key: <LOYALTY_ADMIN_KEY>
{ "contact": "client@email.com", "invoice_id": "INV-2026-0142", "amount_sgd": 800 }
```

This is idempotent — safe to call more than once with the same invoice_id, it will
only credit points the first time. If the client was referred, their referrer is
credited automatically on the client's first booking.

## QR codes

Generate a QR pointing at `https://t.me/YourBotName?start=<referral_code>` (or, for
clients you want going straight to the web portal, `https://loyalty.accurova.sg?ref=<code>`
and prefill the referral field on signup). Print it on invoices, prints, namecards.

## Deploy

Same pattern as your other tools: GitHub -> Zeabur.
- `backend/` deploys as a FastAPI service (serves the web portal as static files too).
- `telegram_bot/` deploys as a second Zeabur service (long-running polling process).
- Set env vars: `LOYALTY_SECRET`, `LOYALTY_ADMIN_KEY`, `TELEGRAM_BOT_TOKEN`, and
  `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` for email OTP delivery.

## Not yet built (next steps)

- Redemption flow (spend points for a discount, applied as a line item in InvoiceForge)
- Admin dashboard for viewing all clients / manual adjustments (currently API-only)
- Signed QR tokens for physical redemption at a shoot (vs. the referral-link QR above)

## License

This project is dual licensed.

**Community Edition** — [GNU Affero General Public License v3 (AGPLv3)](LICENSE). Free to use, modify, and self-host. If you distribute a modified version or run it as a network service, you must make the corresponding source available.

**Commercial License** — for organisations that want to embed, modify, or distribute this software without AGPLv3's obligations. See [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md) and the [agreement template](COMMERCIAL-LICENSE-AGREEMENT-TEMPLATE.md).
