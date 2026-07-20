<div align="center">

# Accurova Loyalty

**One points ledger, three access points: Telegram bot, web portal, QR codes.**

![Python](https://img.shields.io/badge/-Python-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/-FastAPI-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/-SQLite-003B57?logo=sqlite&logoColor=white)
![Zeabur](https://img.shields.io/badge/-Zeabur-6C5CE7)
![License](https://img.shields.io/badge/license-AGPLv3-00D4C8.svg)

</div>

---

## What it does

Accurova Loyalty is a points ledger for service businesses (built alongside InvoiceForge) that lets clients earn and track loyalty points through whichever channel suits them. Telegram-first clients log in via the bot with no OTP required; non-Telegram clients use a web portal with email OTP. Both paths write to the same `clients` and `ledger` tables, and accounts merge automatically if a client later uses both. Referrals are tracked and credited on the referee's first completed booking.

## Features

- Single SQLite ledger shared across all access points — no duplicate records
- Telegram bot entry: `/start`, `/mystatus`, `/refer`, deep-link referral capture
- Web portal entry: phone/email → 6-digit OTP → session token → dashboard (no Telegram required)
- Automatic account merging when a web-first client later starts the Telegram bot
- `POST /api/admin/booking-completed` endpoint — idempotent points crediting on invoice paid
- Automatic referrer credit on a referred client's first completed booking
- QR codes pointing to bot deep-links or web portal with prefilled referral codes

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + SQLite (WAL mode) |
| Frontend | Single-file HTML (web portal) |
| Bot | python-telegram-bot (polling) |
| Hosting | Zeabur (GitHub CI/CD, two services) |

## Quick Start

```bash
git clone https://github.com/TheBooleanJulian/accurova-loyalty
cd accurova-loyalty/backend
pip install -r requirements.txt
cp .env.example .env   # fill in env vars below
python main.py
```

For the bot, in a separate terminal:

```bash
cd telegram_bot
pip install -r requirements.txt   # if separate
python bot.py
```

## Configuration

| Variable | Required | Description |
|---|---|---|
| `LOYALTY_SECRET` | ✅ | Signs session tokens for web portal auth |
| `LOYALTY_ADMIN_KEY` | ✅ | Protects admin endpoints (e.g. booking-completed) |
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `SMTP_HOST` | ✅ | SMTP server for email OTP delivery |
| `SMTP_PORT` | ✅ | SMTP port |
| `SMTP_USER` | ✅ | SMTP login username |
| `SMTP_PASS` | ✅ | SMTP login password |

## Project Structure

```
accurova-loyalty/
├── backend/
│   ├── main.py          — FastAPI app: web portal API + admin endpoints
│   ├── database.py      — SQLite schema (WAL mode), clients + ledger + otp_codes tables
│   ├── ledger.py        — add_entry() / get_balance() / record_booking_completed()
│   ├── auth.py          — OTP generation + verification, session tokens
│   └── requirements.txt
├── telegram_bot/
│   └── bot.py           — /start /mystatus /refer, deep-link referral capture
├── web/
│   └── index.html       — client portal: phone/email → OTP → dashboard
├── LICENSE
├── COMMERCIAL-LICENSE.md
└── NOTICE
```

## Deployment

Two services deployed on Zeabur via GitHub CI/CD:

- **`backend/`** — FastAPI service; also serves the web portal as static files.
- **`telegram_bot/`** — long-running polling process as a separate Zeabur service.

Push to `main` triggers deploy for both services.

## Wiring up InvoiceForge

When an invoice is marked paid, call:

```
POST /api/admin/booking-completed
X-Admin-Key: <LOYALTY_ADMIN_KEY>
{ "contact": "client@email.com", "invoice_id": "INV-2026-0142", "amount_sgd": 800 }
```

Idempotent — safe to call more than once with the same `invoice_id`; points are only credited the first time.

## Status / Roadmap

- [x] SQLite ledger with WAL mode
- [x] Telegram bot (login, status, referrals)
- [x] Web portal with email OTP auth
- [x] Automatic account merging across entry points
- [x] Idempotent booking-completed endpoint with referrer crediting
- [x] QR code referral links (bot deep-link + web portal)
- [ ] Redemption flow (spend points as a discount line item in InvoiceForge)
- [ ] Admin dashboard for client list and manual adjustments (currently API-only)
- [ ] Signed QR tokens for physical redemption at a shoot

## Changelog

- **Jul 2026** — Switched to dual licensing: AGPLv3 for community use, commercial license option added; removed earlier template agreement
- **Jul 2026** — Initial release: FastAPI backend with SQLite ledger, Telegram bot with referral deep-links, single-file HTML web portal with OTP auth

## License

Dual-licensed:
- **Community edition** — [AGPLv3](LICENSE)
- **Commercial use** — see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)

---

<div align="center">
<sub>Built by <a href="https://github.com/TheBooleanJulian">@TheBooleanJulian</a></sub>
</div>