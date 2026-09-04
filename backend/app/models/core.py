"""Customer, payment method, subscription, and invoice — seed-populated in
Phase 1 (see scripts/seed_demo_data.py), not yet exposed via CRUD endpoints.
They exist to give payment_attempts and cases something real to reference."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    plan_tier: Mapped[str] = mapped_column(String(40), default="standard")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    brand: Mapped[str] = mapped_column(String(30))
    last4: Mapped[str] = mapped_column(String(4))
    exp_month: Mapped[int] = mapped_column(Integer)
    exp_year: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    plan_tier: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    # Named "cents" for historical reasons — the value is always the
    # smallest currency unit (cents or paise; the scaling is identical),
    # and app/ml/schema.py::NUMERIC_FEATURES + the already-trained model
    # artifact reference this exact key name. Renaming it would mean
    # threading a rename through the ML feature pipeline right before a
    # demo for a purely cosmetic gain — not worth the risk. See DESIGN.md.
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="inr")
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | paid | void
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
