from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive-UTC now — matches the DB's naive DateTime columns.

    datetime.utcnow() is deprecated since Python 3.12; this is the drop-in
    replacement used everywhere the app needs a naive UTC timestamp.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
