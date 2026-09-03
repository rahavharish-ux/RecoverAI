from datetime import datetime, timezone


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite has no timestamp-with-timezone type, so DateTime(timezone=True)
    columns round-trip as naive datetimes on it (Postgres preserves tzinfo
    natively). Every value this app writes is UTC by convention, so a naive
    read is normalized back to an aware one here — call this at any point
    a DB-read timestamp is compared against or subtracted from a
    `datetime.now(timezone.utc)`-derived value."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
