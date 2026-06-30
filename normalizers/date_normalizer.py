"""
Date Normalizer.

Normalizes dates to YYYY-MM format as required by the assignment.
Handles various input formats:
- "Jan 2020", "January 2020" → "2020-01"
- "2020-01-15" → "2020-01"
- "01/2020" → "2020-01"
- "2020" → "2020-01" (assumes January)
- "Present", "Current" → None (kept as-is)

Uses dateparser for robust multi-format parsing.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import dateparser

logger = logging.getLogger(__name__)


def normalize_date(raw_date: str) -> tuple[Optional[str], bool]:
    """Normalize a date string to YYYY-MM format.

    Args:
        raw_date: Raw date string in any format.

    Returns:
        Tuple of (normalized_date, success).
        Returns (None, True) for "Present"/"Current".
        Returns (raw_date, False) if parsing fails.
    """
    raw_date = raw_date.strip()
    if not raw_date:
        return None, False

    # Handle special values
    if raw_date.lower() in ("present", "current", "now", "ongoing"):
        return None, True

    # Try direct pattern matching first (faster than dateparser)
    # YYYY-MM
    match = re.match(r"^(\d{4})-(\d{1,2})$", raw_date)
    if match:
        year, month = match.groups()
        return f"{year}-{int(month):02d}", True

    # YYYY-MM-DD
    match = re.match(r"^(\d{4})-(\d{1,2})-\d{1,2}$", raw_date)
    if match:
        year, month = match.groups()
        return f"{year}-{int(month):02d}", True

    # MM/YYYY or MM-YYYY
    match = re.match(r"^(\d{1,2})[/\-](\d{4})$", raw_date)
    if match:
        month, year = match.groups()
        return f"{year}-{int(month):02d}", True

    # Just a year
    match = re.match(r"^(19|20)\d{2}$", raw_date)
    if match:
        return f"{raw_date}-01", True

    # Fallback to dateparser for natural language dates
    try:
        parsed = dateparser.parse(
            raw_date,
            settings={
                "PREFER_DATES_FROM": "past",
                "REQUIRE_PARTS": ["year"],
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )
        if parsed:
            result = f"{parsed.year}-{parsed.month:02d}"
            if result != raw_date:
                logger.debug("Date normalized: %s → %s", raw_date, result)
            return result, True
    except Exception as e:
        logger.warning("dateparser failed on '%s': %s", raw_date, e)

    logger.warning("Could not normalize date: '%s'", raw_date)
    return raw_date, False


def normalize_dates_in_experience(
    experience: list[dict],
) -> tuple[list[dict], list[dict[str, str]]]:
    """Normalize start and end dates in experience entries.

    Args:
        experience: List of experience dictionaries.

    Returns:
        Tuple of:
        - Updated experience list with normalized dates
        - List of transformation records for audit
    """
    transformations: list[dict[str, str]] = []
    normalized_exp: list[dict] = []

    for entry in experience:
        new_entry = dict(entry)

        for date_field in ("start", "end"):
            raw = entry.get(date_field)
            if raw and isinstance(raw, str):
                norm_date, success = normalize_date(raw)
                if norm_date != raw:
                    transformations.append({
                        "field": f"experience.{date_field}",
                        "type": "normalization",
                        "before": raw,
                        "after": str(norm_date),
                        "success": str(success),
                    })
                new_entry[date_field] = norm_date

        normalized_exp.append(new_entry)

    return normalized_exp, transformations
