"""Phase 1 seed data — a handful of synthetic customers, payment methods,
subscriptions, and open invoices so the API can be exercised end to end.

This is deliberately small and illustrative, not the statistically
validated synthetic generator described in the approved blueprint (§10) —
that belongs to Phase 2, where it needs to support honest ML evaluation.

Run from backend/:  python -m scripts.seed_demo_data
"""

from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal, engine
from app.models import Base
from app.models.core import Customer, Invoice, PaymentMethod, Subscription

DEMO_CUSTOMERS = [
    {"name": "Priya Raman", "email": "priya@example.com", "plan_tier": "growth", "amount_cents": 2900},
    {"name": "Daniel Osei", "email": "daniel@example.com", "plan_tier": "standard", "amount_cents": 1900},
    {"name": "Mei Lin Tan", "email": "meilin@example.com", "plan_tier": "enterprise", "amount_cents": 19900},
    {"name": "Carlos Rivas", "email": "carlos@example.com", "plan_tier": "standard", "amount_cents": 4900},
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Customer).first() is not None:
            print("Seed data already present — skipping.")
            return

        now = datetime.now(timezone.utc)
        for i, c in enumerate(DEMO_CUSTOMERS):
            customer = Customer(name=c["name"], email=c["email"], plan_tier=c["plan_tier"])
            db.add(customer)
            db.flush()

            method = PaymentMethod(
                customer_id=customer.id,
                brand="visa" if i % 2 == 0 else "mastercard",
                last4=f"{4242 + i:04d}"[-4:],
                exp_month=((i * 3) % 12) + 1,
                exp_year=now.year if i == 2 else now.year + 2,  # one card near/at expiry
            )
            db.add(method)
            db.flush()

            subscription = Subscription(customer_id=customer.id, plan_tier=c["plan_tier"], status="active")
            db.add(subscription)
            db.flush()

            invoice = Invoice(
                subscription_id=subscription.id,
                customer_id=customer.id,
                amount_cents=c["amount_cents"],
                currency="usd",
                due_date=now + timedelta(days=1),
                status="open",
            )
            db.add(invoice)

        db.commit()
        print(f"Seeded {len(DEMO_CUSTOMERS)} customers with active subscriptions and open invoices.")
        print("All data is synthetic and confined to the local sandbox database.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
