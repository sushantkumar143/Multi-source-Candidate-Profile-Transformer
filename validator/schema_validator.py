"""
Schema Validator.

Validates the final projected output against expected schema
before writing to disk. Provides detailed error messages.
"""

from __future__ import annotations

import logging
from typing import Any

from schemas.output_schema import validate_output, validate_canonical_profile

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validates output data against expected schemas."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(
        self,
        output: dict[str, Any],
        is_projected: bool = False,
    ) -> bool:
        """Validate the output data.

        Args:
            output: The output dictionary to validate.
            is_projected: If True, validates as projected output (looser).
                         If False, validates as full canonical profile (strict).

        Returns:
            True if validation passed.
        """
        self.errors = []
        self.warnings = []

        if is_projected:
            is_valid, errors = validate_output(output)
        else:
            is_valid, errors = validate_canonical_profile(output)

        if not is_valid:
            self.errors.extend(errors)
            for error in errors:
                logger.warning("Validation error: %s", error)
        else:
            logger.info("Output validation passed")

        # Additional quality checks
        self._check_quality(output)

        return is_valid

    def _check_quality(self, output: dict[str, Any]) -> None:
        """Run quality checks on the output."""
        # Check for empty strings that should be null
        for key, value in output.items():
            if isinstance(value, str) and value.strip() == "":
                self.warnings.append(f"Field '{key}' is an empty string — consider setting to null")

        # Check for reasonable confidence
        confidence = output.get("overall_confidence")
        if isinstance(confidence, (int, float)):
            if confidence == 0.0:
                self.warnings.append("Overall confidence is 0.0 — profile may be missing critical data")
            elif confidence > 0.95:
                self.warnings.append(f"Overall confidence is very high ({confidence}) — verify accuracy")

        # Check emails format
        emails = output.get("emails", [])
        if isinstance(emails, list):
            for email in emails:
                if isinstance(email, str) and "@" not in email:
                    self.warnings.append(f"Email '{email}' doesn't contain '@'")

        # Check phones format (E.164)
        phones = output.get("phones", [])
        if isinstance(phones, list):
            for phone in phones:
                if isinstance(phone, str) and not phone.startswith("+"):
                    self.warnings.append(f"Phone '{phone}' is not in E.164 format (should start with '+')")
