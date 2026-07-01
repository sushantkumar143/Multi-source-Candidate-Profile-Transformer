"""
Confidence Engine.

Computes deterministic, explainable confidence scores for each field
and for the overall profile. NO random confidence — every score is
derived from measurable factors:

Per-field confidence:
    FieldConfidence = weighted_mean(
        source_reliability      × 0.30,
        agreement_ratio         × 0.30,
        extraction_confidence   × 0.20,
        normalization_success   × 0.10,
        1 - conflict_ratio      × 0.10,
    )

Overall profile confidence:
    OverallConfidence = weighted_mean(field_confidences) × completeness_factor
    where completeness_factor = filled_fields / total_fields
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import Settings

logger = logging.getLogger(__name__)


# All canonical fields (for completeness calculation)
ALL_CANONICAL_FIELDS: list[str] = [
    "full_name",
    "emails",
    "phones",
    "location",
    "links",
    "headline",
    "years_experience",
    "skills",
    "experience",
    "education",
]

# Field importance weights for overall confidence
FIELD_WEIGHTS: dict[str, float] = {
    "full_name": 1.5,       # Critical
    "emails": 1.2,          # Very important
    "phones": 1.0,
    "location": 0.8,
    "links": 0.5,
    "headline": 0.6,
    "years_experience": 0.7,
    "skills": 1.0,
    "experience": 1.2,
    "education": 0.8,
}


class ConfidenceEngine:
    """Computes explainable confidence scores for the profile."""

    def __init__(self) -> None:
        self.field_confidences: dict[str, float] = {}
        self.field_explanations: dict[str, dict[str, Any]] = {}

    def compute(
        self,
        merged_data: dict[str, Any],
        source_contributions: dict[str, list[str]],
        normalization_results: dict[str, bool],
        conflicts: list[dict[str, Any]],
        extraction_confidences: dict[str, float],
    ) -> tuple[dict[str, float], float]:
        """Compute per-field and overall confidence scores.

        Args:
            merged_data: The merged canonical data.
            source_contributions: {field: [sources that contributed]}.
            normalization_results: {field: was_normalization_successful}.
            conflicts: List of conflict records from the merger.
            extraction_confidences: {source: extraction_confidence_score}.

        Returns:
            Tuple of:
            - dict of field_name → confidence (0.0-1.0)
            - overall_confidence (0.0-1.0)
        """
        self.field_confidences = {}
        self.field_explanations = {}
        conflict_fields = {c["field"] for c in conflicts}

        for field_name in ALL_CANONICAL_FIELDS:
            has_value = self._field_has_value(field_name, merged_data)
            if not has_value:
                self.field_confidences[field_name] = 0.0
                self.field_explanations[field_name] = {"reason": "missing"}
                continue

            sources = source_contributions.get(field_name, [])
            total_sources = len(set(s for s in extraction_confidences.keys()))

            # Factor 1: Source reliability (0.30)
            if sources:
                source_rel = max(
                    Settings.SOURCE_RELIABILITY.get(s, 0.5) for s in sources
                )
            else:
                source_rel = 0.0

            # Factor 2: Agreement ratio (0.30)
            if total_sources > 0 and sources:
                agreement_ratio = len(sources) / total_sources
            else:
                agreement_ratio = 0.0

            # Factor 3: Extraction confidence (0.20)
            if sources:
                ext_confs = [
                    extraction_confidences.get(s, 0.5) for s in sources
                ]
                avg_extraction = sum(ext_confs) / len(ext_confs)
            else:
                avg_extraction = 0.0

            # Factor 4: Normalization success (0.10)
            norm_success = 1.0 if normalization_results.get(field_name, True) else 0.5

            # Factor 5: Conflict ratio (0.10)
            has_conflict = 1.0 if field_name in conflict_fields else 0.0
            conflict_score = 1.0 - has_conflict

            # Weighted confidence
            confidence = (
                source_rel * Settings.CONFIDENCE_WEIGHT_SOURCE
                + agreement_ratio * Settings.CONFIDENCE_WEIGHT_AGREEMENT
                + avg_extraction * Settings.CONFIDENCE_WEIGHT_EXTRACTION
                + norm_success * Settings.CONFIDENCE_WEIGHT_NORMALIZATION
                + conflict_score * Settings.CONFIDENCE_WEIGHT_CONFLICT
            )

            # Clamp to [0, 1]
            confidence = max(0.0, min(1.0, confidence))
            self.field_confidences[field_name] = round(confidence, 3)

            self.field_explanations[field_name] = {
                "source_reliability": round(source_rel, 3),
                "agreement_ratio": round(agreement_ratio, 3),
                "extraction_confidence": round(avg_extraction, 3),
                "normalization_success": norm_success,
                "conflict_free": conflict_score,
                "computed_confidence": round(confidence, 3),
            }

        # Overall confidence
        overall = self._compute_overall(merged_data)

        logger.info(
            "Confidence computed: %d fields scored, overall=%.3f",
            len(self.field_confidences),
            overall,
        )

        return self.field_confidences, overall

    def _compute_overall(self, merged_data: dict[str, Any]) -> float:
        """Compute overall profile confidence.

        overall = weighted_mean(field_confidences) × completeness_factor
        """
        # Weighted mean of field confidences
        total_weight = 0.0
        weighted_sum = 0.0

        for field_name, confidence in self.field_confidences.items():
            weight = FIELD_WEIGHTS.get(field_name, 1.0)
            weighted_sum += confidence * weight
            total_weight += weight

        if total_weight > 0:
            weighted_avg = weighted_sum / total_weight
        else:
            weighted_avg = 0.0

        # Completeness factor based on core fields only to avoid penalizing optional fields
        core_fields = ["full_name", "emails", "skills", "experience"]
        filled = sum(
            1
            for f in core_fields
            if self._field_has_value(f, merged_data)
        )
        completeness = min(1.0, filled / len(core_fields) + 0.1) # small boost for having fields

        overall = weighted_avg * completeness
        return round(max(0.0, min(1.0, overall)), 3)

    @staticmethod
    def _field_has_value(field_name: str, data: dict[str, Any]) -> bool:
        """Check if a field has a meaningful value."""
        value = data.get(field_name)
        if value is None:
            return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        return True
