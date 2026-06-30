"""
Deduplicator.

Removes duplicate values from list fields while preserving order.
Deduplication is case-insensitive for strings.

Handles:
- Duplicate emails (case-insensitive)
- Duplicate phone numbers (after normalization)
- Duplicate skills (case-insensitive)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def deduplicate(
    values: list[Any],
    case_insensitive: bool = True,
) -> tuple[list[Any], list[dict[str, str]]]:
    """Remove duplicates from a list while preserving order.

    Args:
        values: List of values to deduplicate.
        case_insensitive: If True, comparison is case-insensitive for strings.

    Returns:
        Tuple of:
        - Deduplicated list (preserving first occurrence order)
        - List of removed duplicates for audit
    """
    seen: set[str] = set()
    result: list[Any] = []
    duplicates: list[dict[str, str]] = []

    for value in values:
        if isinstance(value, str):
            key = value.lower() if case_insensitive else value
        else:
            key = str(value)

        if key in seen:
            duplicates.append({
                "field": "dedup",
                "type": "duplicate_removed",
                "value": str(value),
            })
            logger.debug("Duplicate removed: %s", value)
        else:
            seen.add(key)
            result.append(value)

    return result, duplicates


def deduplicate_emails(emails: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    """Deduplicate email addresses (case-insensitive).

    Args:
        emails: List of email addresses.

    Returns:
        Tuple of (deduplicated_emails, audit_records).
    """
    # Normalize: lowercase all emails
    normalized = [e.strip().lower() for e in emails if e and e.strip()]
    result, dupes = deduplicate(normalized, case_insensitive=True)
    for d in dupes:
        d["field"] = "emails"
    return result, dupes


def deduplicate_phones(phones: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    """Deduplicate phone numbers.

    Args:
        phones: List of phone numbers (ideally already E.164).

    Returns:
        Tuple of (deduplicated_phones, audit_records).
    """
    result, dupes = deduplicate(phones, case_insensitive=False)
    for d in dupes:
        d["field"] = "phones"
    return result, dupes


def deduplicate_skills(skills: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    """Deduplicate skill names (case-insensitive).

    Args:
        skills: List of skill names.

    Returns:
        Tuple of (deduplicated_skills, audit_records).
    """
    result, dupes = deduplicate(skills, case_insensitive=True)
    for d in dupes:
        d["field"] = "skills"
    return result, dupes
