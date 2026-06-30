"""
Phone Normalizer.

Normalizes phone numbers to E.164 format using the `phonenumbers` library.
Handles various input formats:
- 9876543210 → +919876543210
- +1-555-123-4567 → +15551234567
- (555) 123-4567 → +15551234567
- +91 98765 43210 → +919876543210

Falls back to best-effort cleaning if phonenumbers can't parse.
"""

from __future__ import annotations

import logging
import re

import phonenumbers

from config.settings import Settings

logger = logging.getLogger(__name__)


def normalize_phone(
    raw_phone: str,
    default_region: str | None = None,
) -> tuple[str, bool]:
    """Normalize a single phone number to E.164 format.

    Args:
        raw_phone: Raw phone number string.
        default_region: ISO country code for numbers without country code.
                       Defaults to Settings.DEFAULT_PHONE_REGION.

    Returns:
        Tuple of (normalized_phone, success).
        If normalization fails, returns the cleaned raw phone and False.
    """
    if default_region is None:
        default_region = Settings.DEFAULT_PHONE_REGION

    raw_phone = raw_phone.strip()
    if not raw_phone:
        return "", False

    try:
        parsed = phonenumbers.parse(raw_phone, default_region)
        if phonenumbers.is_valid_number(parsed):
            formatted = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
            if formatted != raw_phone:
                logger.debug("Phone normalized: %s → %s", raw_phone, formatted)
            return formatted, True
        else:
            # Try without region (maybe it has a full country code)
            if not raw_phone.startswith("+"):
                parsed_intl = phonenumbers.parse("+" + raw_phone, None)
                if phonenumbers.is_valid_number(parsed_intl):
                    formatted = phonenumbers.format_number(
                        parsed_intl, phonenumbers.PhoneNumberFormat.E164
                    )
                    return formatted, True

            logger.warning("Phone number not valid: %s", raw_phone)
            # Return cleaned version
            cleaned = re.sub(r"[^\d+]", "", raw_phone)
            return cleaned, False

    except phonenumbers.NumberParseException as e:
        logger.warning("Could not parse phone number '%s': %s", raw_phone, e)
        cleaned = re.sub(r"[^\d+]", "", raw_phone)
        return cleaned, False


def normalize_phones(
    phones: list[str],
    default_region: str | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    """Normalize a list of phone numbers to E.164 format.

    Args:
        phones: List of raw phone number strings.
        default_region: Default country code for region-less numbers.

    Returns:
        Tuple of:
        - List of normalized phone numbers (E.164)
        - List of transformation records for audit
    """
    normalized: list[str] = []
    transformations: list[dict[str, str]] = []

    for phone in phones:
        result, success = normalize_phone(phone, default_region)
        if result:
            normalized.append(result)
            if result != phone.strip():
                transformations.append({
                    "field": "phone",
                    "type": "normalization",
                    "before": phone.strip(),
                    "after": result,
                    "success": str(success),
                })

    return normalized, transformations
