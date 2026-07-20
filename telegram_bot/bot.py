"""
Accurova Loyalty Telegram bot.
Run: python bot.py  (needs TELEGRAM_BOT_TOKEN env var)

Deep link format: t.me/YourBotName?start=JUL-4F2K  (referral code auto-attached)
"""
import os
import sys

sys.path.append("../backend")
import ledger  # noqa: E402
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    referral_code = context.args[0] if context.args else None

    client = ledger.get_or_create_client(
        telegram_id=tg_user.id,
        name=tg_user.first_name,
        referred_by_code=referral_code,
    )

    if referral_code and client["referred_by_client_id"]:
        await update.message.reply_text(
            f"Welcome to Accurova Loyalty, {tg_user.first_name}!\n\n"
            f"You were referred — your friend gets 100 points once you complete your first shoot with us.\n\n"
            f"Your own referral code is {client['referral_code']} — share it to start earning too."
        )
    else:
        await update.message.reply_text(
            f"Welcome to Accurova Loyalty, {tg_user.first_name}!\n\n"
            f"Your referral code is {client['referral_code']}. Share it — you'll earn 100 points "
            f"whenever someone books their first shoot using it.\n\n"
            f"Use /mystatus anytime to check your balance."
        )


async def mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    client = ledger.get_or_create_client(telegram_id=tg_user.id, name=tg_user.first_name)
    balance = ledger.get_balance(client["id"])
    await update.message.reply_text(
        f"Your balance: {balance} points\n"
        f"Referral code: {client['referral_code']}\n\n"
        f"Use /refer to get your shareable link."
    )


async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    client = ledger.get_or_create_client(telegram_id=tg_user.id, name=tg_user.first_name)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={client['referral_code']}"
    await update.message.reply_text(
        f"Share this link — you get 100 points when they complete their first shoot:\n\n{link}"
    )


async def send_otp(telegram_id: int, code: str, bot):
    """Called by the FastAPI backend (or a small internal queue) to deliver web-login codes."""
    await bot.send_message(chat_id=telegram_id, text=f"Your Accurova loyalty portal code: {code}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mystatus", mystatus))
    app.add_handler(CommandHandler("refer", refer))
    app.run_polling()


if __name__ == "__main__":
    main()
