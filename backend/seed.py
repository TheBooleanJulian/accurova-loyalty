"""
Seeds two test clients so you can try the whole flow without needing a real
Telegram bot token or SMTP account yet.

Run: cd backend && python seed.py
"""
from database import init_db
import ledger

init_db()

# "You" as the admin/dev test client — sign in on the web portal with this email.
admin = ledger.get_or_create_client(email="julian@dev.test", name="Julian (dev)")
ledger.add_entry(admin["id"], 250, "adjustment", note="seed: starting balance", created_by="seed")

# A second client who was referred by the admin — simulates the referral flow.
referred = ledger.get_or_create_client(
    email="testclient@dev.test", name="Test Client",
    referred_by_code=admin["referral_code"],
)

print("Seeded two dev clients:\n")
print(f"  Admin/dev account : julian@dev.test   (id={admin['id']}, referral_code={admin['referral_code']}, balance={ledger.get_balance(admin['id'])})")
print(f"  Referred client   : testclient@dev.test (id={referred['id']}, balance={ledger.get_balance(referred['id'])})")
print("\nNext: log in to the web portal with julian@dev.test — since SMTP isn't")
print("configured, the OTP code will print to this terminal instead of being emailed.")
print("\nTo simulate that referred client completing their first booking (which")
print("should credit the admin account +100 referral points), run:\n")
print(f'  curl -X POST http://localhost:8000/api/admin/booking-completed \\')
print(f'    -H "X-Admin-Key: dev-admin-key" -H "Content-Type: application/json" \\')
print(f'    -d \'{{"contact": "testclient@dev.test", "invoice_id": "INV-TEST-001", "amount_sgd": 500}}\'')
