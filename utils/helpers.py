"""
Shared utility functions for the pipeline.

Small, reusable helpers that don't belong to any specific pipeline stage.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


def generate_candidate_id(*identifiers: str) -> str:
    """Generate a deterministic candidate ID from identifying information.

    Uses a SHA-256 hash of lowercased, sorted identifiers so the same
    candidate always produces the same ID regardless of source order.

    Args:
        identifiers: Strings to hash (e.g., name, email).

    Returns:
        A hex string candidate ID (first 12 characters of SHA-256).
    """
    normalized = sorted(s.strip().lower() for s in identifiers if s and s.strip())
    combined = "|".join(normalized)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:12]


def clean_string(value: Any) -> str | None:
    """Clean and normalize a string value.

    Strips whitespace, collapses multiple spaces, returns None for empty.

    Args:
        value: Any value to clean.

    Returns:
        Cleaned string or None.
    """
    if value is None:
        return None
    s = str(value).strip()
    s = re.sub(r"\s+", " ", s)
    return s if s else None


def extract_emails(text: str) -> list[str]:
    """Extract email addresses from text.

    Args:
        text: Input text to search.

    Returns:
        List of lowercase, deduplicated email addresses.
    """
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    matches = re.findall(pattern, text)
    seen: set[str] = set()
    result: list[str] = []
    for email in matches:
        lower = email.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(lower)
    return result


def extract_phone_numbers(text: str) -> list[str]:
    """Extract potential phone numbers from text.

    Uses a broad pattern to capture various phone formats.
    Actual normalization to E.164 is done by the phone normalizer.

    Args:
        text: Input text to search.

    Returns:
        List of raw phone number strings.
    """
    pattern = r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}"
    matches = re.findall(pattern, text)
    # Clean up and deduplicate
    seen: set[str] = set()
    result: list[str] = []
    for match in matches:
        cleaned = re.sub(r"[\s\-.()\u2013\u2014]", "", match)
        if len(cleaned) >= 7 and cleaned not in seen:
            seen.add(cleaned)
            result.append(match.strip())
    return result


def safe_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get a value from a dictionary with a default.

    Also handles None values by returning the default.

    Args:
        data: Dictionary to search.
        key: Key to look up.
        default: Default value if key not found or value is None.

    Returns:
        The value or default.
    """
    value = data.get(key, default)
    return default if value is None else value


def flatten_list(nested: list[Any]) -> list[Any]:
    """Flatten a potentially nested list one level deep.

    Args:
        nested: List that may contain sublists.

    Returns:
        Flattened list.
    """
    result: list[Any] = []
    for item in nested:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result
