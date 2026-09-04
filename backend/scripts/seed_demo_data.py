"""Seed data for local dev/demo — realistic Indian customer names and
order values, run through the real ingestion pipeline (the same
`ingestion_service.record_payment_attempt` the API and Demo Center use)
so a fresh sandbox already has a believable caseload: diagnosed, scored,
and policy-evaluated, exactly as if each attempt had arrived from a real
gateway webhook.

Deliberately does NOT pre-seed any resolved/recovered case — recovery
only ever happens through a real agent decision or a real direct action,
triggered by a person or the Demo Center. Pre-baking a "success" here
would mean showing a number on the dashboard that no decision actually
produced, which is exactly the kind of fabricated metric this project
does not allow anywhere else.

Amounts are realistic Indian order values (non-round, paise-level
variance) rather than the round demo numbers a payments person clocks as
fake on sight. At least three exceed ₹99,999 so the app's Indian digit
grouping (₹1,24,500 style) is actually exercised on screen, not just
implemented and never seen. Decline reasons are weighted the way they
occur in practice — mostly soft, recoverable declines; hard declines and
fraud signals are rare, not evenly distributed across the roster.

Run from backend/:  python -m scripts.seed_demo_data
"""

import random
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal, engine
from app.domain.enums import AttemptSource, DeclineCode
from app.models import Base
from app.models.core import Customer, Invoice, PaymentMethod, Subscription
from app.services import ingestion_service

SEED = 20260905  # fixed — the same run always produces the same demo caseload

# tenure_days / method_age_days backdate the customer and card so
# PREDICT-stage features (customer_tenure_days, payment_method_age_days)
# read realistically instead of ~0 — matching the range the training
# data was generated over (see training/synthetic_data.py). amount_cents
# is the real order value in integer cents (paise); decline_code drives
# what ingestion diagnoses this attempt as.
DEMO_CUSTOMERS = [
    {"name": "Priya Raman", "email": "priya.raman@example.in", "plan_tier": "growth",
     "amount_cents": 284750, "tenure_days": 620, "method_age_days": 540,
     "decline_code": DeclineCode.PROCESSOR_ERROR},
    {"name": "Arjun Mehta", "email": "arjun.mehta@example.in", "plan_tier": "standard",
     "amount_cents": 1842387, "tenure_days": 88, "method_age_days": 60,
     "decline_code": DeclineCode.INSUFFICIENT_FUNDS},
    {"name": "Sneha Kulkarni", "email": "sneha.kulkarni@example.in", "plan_tier": "standard",
     "amount_cents": 94520, "tenure_days": 34, "method_age_days": 34,
     "decline_code": DeclineCode.INSUFFICIENT_FUNDS},
    {"name": "Rohan Verma", "email": "rohan.verma@example.in", "plan_tier": "enterprise",
     "amount_cents": 12478000, "tenure_days": 910, "method_age_days": 700,
     "decline_code": DeclineCode.CARD_DECLINED},
    {"name": "Ananya Iyer", "email": "ananya.iyer@example.in", "plan_tier": "growth",
     "amount_cents": 621565, "tenure_days": 275, "method_age_days": 200,
     "decline_code": DeclineCode.INSUFFICIENT_FUNDS},
    {"name": "Vikram Nair", "email": "vikram.nair@example.in", "plan_tier": "standard",
     "amount_cents": 38999, "tenure_days": 12, "method_age_days": 12,
     "decline_code": DeclineCode.EXPIRED_CARD},
    {"name": "Kavita Desai", "email": "kavita.desai@example.in", "plan_tier": "enterprise",
     "amount_cents": 28499950, "tenure_days": 1240, "method_age_days": 1100,
     "decline_code": DeclineCode.CARD_DECLINED},
    {"name": "Rahul Chatterjee", "email": "rahul.chatterjee@example.in", "plan_tier": "standard",
     "amount_cents": 1265030, "tenure_days": 150, "method_age_days": 150,
     "decline_code": DeclineCode.INSUFFICIENT_FUNDS},
    {"name": "Meera Pillai", "email": "meera.pillai@example.in", "plan_tier": "growth",
     "amount_cents": 342000, "tenure_days": 402, "method_age_days": 60,
     "decline_code": DeclineCode.PROCESSOR_ERROR},
    {"name": "Suresh Reddy", "email": "suresh.reddy@example.in", "plan_tier": "enterprise",
     "amount_cents": 31575025, "tenure_days": 1680, "method_age_days": 1500,
     "decline_code": DeclineCode.DO_NOT_HONOR},
    {"name": "Divya Bhatt", "email": "divya.bhatt@example.in", "plan_tier": "standard",
     "amount_cents": 72545, "tenure_days": 5, "method_age_days": 5,
     "decline_code": DeclineCode.INVALID_METHOD},
    {"name": "Karan Malhotra", "email": "karan.malhotra@example.in", "plan_tier": "growth",
     "amount_cents": 989999, "tenure_days": 340, "method_age_days": 340,
     "decline_code": DeclineCode.INSUFFICIENT_FUNDS},
    {"name": "Fatima Sheikh", "email": "fatima.sheikh@example.in", "plan_tier": "standard",
     "amount_cents": 154075, "tenure_days": 61, "method_age_days": 61,
     "decline_code": DeclineCode.CARD_DECLINED},
    {"name": "Aditya Krishnan", "email": "aditya.krishnan@example.in", "plan_tier": "standard",
     "amount_cents": 2831020, "tenure_days": 190, "method_age_days": 25,
     "decline_code": DeclineCode.EXPIRED_CARD},
]

_CARD_BRANDS = ["visa", "mastercard", "rupay"]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Customer).first() is not None:
            print("Seed data already present — skipping.")
            return

        rng = random.Random(SEED)
        now = datetime.now(timezone.utc)

        for i, c in enumerate(DEMO_CUSTOMERS):
            customer = Customer(
                name=c["name"],
                email=c["email"],
                plan_tier=c["plan_tier"],
                created_at=now - timedelta(days=c["tenure_days"]),
            )
            db.add(customer)
            db.flush()

            method = PaymentMethod(
                customer_id=customer.id,
                brand=_CARD_BRANDS[i % len(_CARD_BRANDS)],
                last4=f"{rng.randint(1000, 9999)}",
                exp_month=rng.randint(1, 12),
                exp_year=now.year if c["decline_code"] == DeclineCode.EXPIRED_CARD else now.year + rng.randint(1, 3),
                created_at=now - timedelta(days=c["method_age_days"]),
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
                currency="inr",
                due_date=now + timedelta(days=1),
                status="open",
                created_at=now - timedelta(days=2),
            )
            db.add(invoice)
            db.flush()

            # Stagger attempts across the last few days rather than
            # stamping every case "just now" — a real caseload didn't all
            # fail in the same second.
            attempted_at = now - timedelta(hours=i * 7 + rng.randint(0, 5), minutes=rng.randint(0, 59))

            ingestion_service.record_payment_attempt(
                db,
                invoice=invoice,
                payment_method_id=method.id,
                amount_cents=c["amount_cents"],
                currency="inr",
                decline_code=c["decline_code"],
                source=AttemptSource.EXTERNAL,
                attempted_at=attempted_at,
            )

        print(f"Seeded {len(DEMO_CUSTOMERS)} customers with a diagnosed, scored, policy-evaluated caseload.")
        print("No case was pre-resolved — every recovery on the dashboard comes from a real decision.")
        print("All data is synthetic and confined to the local sandbox database.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
