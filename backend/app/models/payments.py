from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import AttemptSource, AttemptStatus, DeclineClass, DeclineCode
from app.models.base import Base, utcnow


class PaymentAttempt(Base):
    """Every attempt to settle an invoice — the initial gateway failure or a
    later retry. A retry produces a new row here just like the original
    attempt did, so Diagnose and Audit treat both identically."""

    __tablename__ = "payment_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    payment_method_id: Mapped[int] = mapped_column(ForeignKey("payment_methods.id"))
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    # Named "cents" for historical reasons — the value is always the
    # smallest currency unit (cents or paise; the scaling is identical),
    # and app/ml/schema.py::NUMERIC_FEATURES + the already-trained model
    # artifact reference this exact key name. Renaming it would mean
    # threading a rename through the ML feature pipeline right before a
    # demo for a purely cosmetic gain — not worth the risk. See DESIGN.md.
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="inr")
    # A real, persisted Razorpay-shaped identifier, generated once at
    # ingestion (see services/ingestion_service.py) and never regenerated
    # — the same pattern a real gateway uses (assign an opaque id at
    # creation, return it forever after). Deliberately NOT derived from
    # the row's own integer id, and deliberately NOT computed on the fly
    # at render time: a per-render "fake" id would be exactly the kind of
    # decorative, non-stored data this project's no-fabrication rule
    # exists to rule out.
    gateway_payment_id: Mapped[str] = mapped_column(String(20))
    status: Mapped[AttemptStatus] = mapped_column(SAEnum(AttemptStatus, native_enum=False, length=20))
    decline_code: Mapped[DeclineCode | None] = mapped_column(
        SAEnum(DeclineCode, native_enum=False, length=30), nullable=True
    )
    decline_class: Mapped[DeclineClass | None] = mapped_column(
        SAEnum(DeclineClass, native_enum=False, length=10), nullable=True
    )
    source: Mapped[AttemptSource] = mapped_column(SAEnum(AttemptSource, native_enum=False, length=20))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    external_event_id: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
