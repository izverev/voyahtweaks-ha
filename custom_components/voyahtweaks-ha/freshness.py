"""Telemetry freshness helpers (no Home Assistant dependencies)."""

from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any


def parse_last_seen(value: Any) -> datetime | None:
    """Parse the ``last_seen`` field into an aware UTC datetime.

    The exact format is not confirmed against the live API, so we accept:
    ISO-8601 strings (naive values are treated as UTC), epoch seconds and
    epoch milliseconds (as numbers or numeric strings).
    Anything else yields ``None`` (freshness unknown).
    """
    if value is None or isinstance(value, bool):
        return None

    number: float | None = None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            number = None
        if number is None:
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
    else:
        return None

    if number is None or not math.isfinite(number) or number <= 0:
        return None
    if number > 1e11:  # milliseconds
        number /= 1000.0
    try:
        return datetime.fromtimestamp(number, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def compute_age_seconds(last_seen: datetime | None, now: datetime) -> float | None:
    """Return age of the data in seconds (never negative) or None."""
    if last_seen is None:
        return None
    return max(0.0, (now - last_seen).total_seconds())


def is_fresh(age_seconds: float | None, threshold_seconds: float) -> bool | None:
    """True if the data is fresh, False if stale, None if unknown."""
    if age_seconds is None:
        return None
    return age_seconds <= threshold_seconds
