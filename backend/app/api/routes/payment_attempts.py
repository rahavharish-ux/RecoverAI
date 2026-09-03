from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.serializers import ingest_result_to_schema
from app.db.session import get_db
from app.domain.enums import AttemptSource
from app.models.core import Invoice
from app.schemas.payment_attempt import PaymentAttemptIngestRequest, PaymentAttemptIngestResult
from app.services import ingestion_service

router = APIRouter(prefix="/payment-attempts", tags=["payment-attempts"])


@router.post("", response_model=PaymentAttemptIngestResult, status_code=201)
def ingest_payment_attempt(
    payload: PaymentAttemptIngestRequest, db: Session = Depends(get_db)
) -> PaymentAttemptIngestResult:
    """Detect: record a payment attempt exactly as a gateway webhook would
    report it. Omit `decline_code` for a success; include it for a failure.
    Runs Diagnose, Predict (best-effort), and Decide inline for failures."""
    invoice = db.get(Invoice, payload.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice {payload.invoice_id} not found.")

    result = ingestion_service.record_payment_attempt(
        db,
        invoice=invoice,
        payment_method_id=payload.payment_method_id,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        decline_code=payload.decline_code,
        source=AttemptSource.EXTERNAL,
        external_event_id=payload.external_event_id,
        attempted_at=payload.attempted_at,
    )
    return ingest_result_to_schema(db, result)
