"""
Output schema validation.

Validates the final projected output against Pydantic models
before writing to disk. Catches type mismatches and missing
required fields.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from schemas.canonical import CanonicalProfile

logger = logging.getLogger(__name__)


def validate_output(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate projected output data.

    Attempts to validate the output against the CanonicalProfile schema.
    For projected (reshaped) outputs, performs structural checks instead.

    Args:
        data: The output dictionary to validate.

    Returns:
        Tuple of (is_valid, list of error/warning messages).
    """
    errors: list[str] = []

    # Basic structural checks
    if not isinstance(data, dict):
        errors.append("Output must be a dictionary")
        return False, errors

    if not data:
        errors.append("Output is empty")
        return False, errors

    # Type checks for known fields
    type_checks: dict[str, type | tuple[type, ...]] = {
        "candidate_id": str,
        "full_name": str,
        "emails": list,
        "phones": list,
        "skills": list,
        "experience": list,
        "education": list,
        "provenance": list,
        "overall_confidence": (int, float),
        "years_experience": (int, float, type(None)),
    }

    for field_name, expected_type in type_checks.items():
        if field_name in data and data[field_name] is not None:
            if not isinstance(data[field_name], expected_type):
                errors.append(
                    f"Field '{field_name}' expected {expected_type.__name__ if isinstance(expected_type, type) else expected_type}, "
                    f"got {type(data[field_name]).__name__}"
                )

    # Validate confidence range
    if "overall_confidence" in data:
        conf = data["overall_confidence"]
        if isinstance(conf, (int, float)) and not (0.0 <= conf <= 1.0):
            errors.append(
                f"overall_confidence must be between 0.0 and 1.0, got {conf}"
            )

    is_valid = len(errors) == 0
    if not is_valid:
        for error in errors:
            logger.warning("Output validation: %s", error)

    return is_valid, errors


def validate_canonical_profile(profile: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate data against the full CanonicalProfile schema.

    Args:
        profile: Dictionary to validate as a CanonicalProfile.

    Returns:
        Tuple of (is_valid, list of error messages).
    """
    try:
        CanonicalProfile(**profile)
        return True, []
    except ValidationError as e:
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        return False, errors
