"""
Audit Engine.

Generates a comprehensive audit report (audit_report.json) that records
every transformation, normalization, conflict resolution, and quality
check performed during pipeline execution.

The audit report serves as a complete lineage trail for explainability
and debugging.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class AuditEngine:
    """Generates audit reports for pipeline runs."""

    def __init__(self) -> None:
        self.start_time: datetime | None = None
        self.transformations: list[dict[str, str]] = []
        self.duplicates_removed: list[dict[str, str]] = []
        self.conflicts: list[dict[str, Any]] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.sources_detected: list[str] = []
        self.normalization_results: dict[str, bool] = {}

    def start(self) -> None:
        """Mark the start of pipeline processing."""
        self.start_time = datetime.now(timezone.utc)

    def add_transformations(self, transformations: list[dict[str, str]]) -> None:
        """Record transformation records."""
        self.transformations.extend(transformations)

    def add_duplicates(self, duplicates: list[dict[str, str]]) -> None:
        """Record duplicate removal records."""
        self.duplicates_removed.extend(duplicates)

    def add_conflicts(self, conflicts: list[dict[str, Any]]) -> None:
        """Record conflict resolution records."""
        self.conflicts.extend(conflicts)

    def add_warning(self, warning: str) -> None:
        """Record a warning."""
        self.warnings.append(warning)
        logger.warning("Audit: %s", warning)

    def add_error(self, error: str) -> None:
        """Record an error."""
        self.errors.append(error)
        logger.error("Audit: %s", error)

    def set_sources(self, sources: list[str]) -> None:
        """Set the list of detected source files."""
        self.sources_detected = sources

    def generate_report(
        self,
        profile_data: dict[str, Any],
        field_confidences: dict[str, float],
    ) -> dict[str, Any]:
        """Generate the complete audit report.

        Args:
            profile_data: The final canonical profile data.
            field_confidences: Per-field confidence scores.

        Returns:
            Audit report dictionary, ready to serialize to JSON.
        """
        end_time = datetime.now(timezone.utc)
        duration_ms = 0
        if self.start_time:
            duration_ms = int((end_time - self.start_time).total_seconds() * 1000)

        # Calculate data quality metrics
        data_quality = self._compute_data_quality(profile_data, field_confidences)

        report: dict[str, Any] = {
            "processing_timestamp": end_time.isoformat(),
            "processing_duration_ms": duration_ms,
            "sources_detected": self.sources_detected,
            "total_transformations": len(self.transformations),
            "transformations": self.transformations,
            "duplicates_removed": self.duplicates_removed,
            "conflicts": self.conflicts,
            "data_quality": data_quality,
            "field_confidences": {
                k: round(v, 3) for k, v in field_confidences.items()
            },
            "warnings": self.warnings,
            "errors": self.errors,
        }

        logger.info(
            "Audit report generated: %d transformations, %d conflicts, %d warnings",
            len(self.transformations),
            len(self.conflicts),
            len(self.warnings),
        )

        return report

    def _compute_data_quality(
        self,
        profile_data: dict[str, Any],
        field_confidences: dict[str, float],
    ) -> dict[str, Any]:
        """Compute data quality metrics for the audit report.

        Returns:
            Data quality section of the audit report.
        """
        all_fields = [
            "full_name", "emails", "phones", "location", "links",
            "headline", "skills", "experience",
            "education",
        ]

        missing_fields: list[str] = []
        filled_fields: list[str] = []

        for field_name in all_fields:
            value = profile_data.get(field_name)
            if value is None:
                missing_fields.append(field_name)
            elif isinstance(value, (list, dict)) and len(value) == 0:
                missing_fields.append(field_name)
            elif isinstance(value, str) and not value.strip():
                missing_fields.append(field_name)
            else:
                filled_fields.append(field_name)

        completeness = len(filled_fields) / len(all_fields) if all_fields else 0.0

        # Fields with conflicts
        conflicting_fields = list({c["field"] for c in self.conflicts})

        # Fields with duplicates
        duplicate_fields = list({d.get("field", "") for d in self.duplicates_removed})

        return {
            "missing_fields": missing_fields,
            "filled_fields": filled_fields,
            "conflicting_fields": conflicting_fields,
            "duplicate_fields": duplicate_fields,
            "profile_completeness": round(completeness, 2),
            "total_fields": len(all_fields),
            "filled_count": len(filled_fields),
            "missing_count": len(missing_fields),
            "warnings": [w for w in self.warnings if "missing" in w.lower() or "empty" in w.lower()],
        }
