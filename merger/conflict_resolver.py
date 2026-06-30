"""
Conflict Resolver — intelligent scoring engine.

When multiple sources provide conflicting values for the same field,
this module uses a scoring formula to select the best value:

Score = SourceReliability × 0.35
      + AgreementBonus × 0.30
      + ExtractionConfidence × 0.25
      - ConflictPenalty × 0.10

The selected value includes:
- selected_value: the chosen value
- reason: human-readable explanation
- confidence: computed confidence score
- sources: which sources supported this value
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class ResolvedField:
    """Result of conflict resolution for a single field."""

    selected_value: Any
    reason: str
    confidence: float
    sources: list[str]
    alternatives: list[dict[str, Any]] = field(default_factory=list)


class ConflictResolver:
    """Resolves conflicts between multiple source values using scoring."""

    def resolve(
        self,
        field_name: str,
        candidates: list[dict[str, Any]],
    ) -> ResolvedField:
        """Resolve a conflict between multiple candidate values.

        Args:
            field_name: The canonical field name with the conflict.
            candidates: List of dicts with keys:
                - source: source name
                - value: the value from this source
                - extraction_confidence: parser-assigned confidence

        Returns:
            ResolvedField with the selected value and explanation.
        """
        if not candidates:
            return ResolvedField(
                selected_value=None,
                reason="No candidates",
                confidence=0.0,
                sources=[],
            )

        if len(candidates) == 1:
            c = candidates[0]
            return ResolvedField(
                selected_value=c["value"],
                reason=f"Only source: {c['source']}",
                confidence=Settings.SOURCE_RELIABILITY.get(c["source"], 0.5),
                sources=[c["source"]],
            )

        # Group candidates by normalized value
        value_groups: dict[str, list[dict[str, Any]]] = {}
        for c in candidates:
            val_key = self._normalize_value_key(c["value"])
            if val_key not in value_groups:
                value_groups[val_key] = []
            value_groups[val_key].append(c)

        total_sources = len(candidates)

        # Score each unique value
        scored: list[tuple[float, str, Any, list[str], str]] = []
        for val_key, group in value_groups.items():
            score, reason = self._compute_score(
                group=group,
                total_sources=total_sources,
                total_unique_values=len(value_groups),
            )
            sources = [c["source"] for c in group]
            value = group[0]["value"]  # Use the value from the first source in this group
            scored.append((score, reason, value, sources, val_key))

        # Sort by score (highest first)
        scored.sort(key=lambda x: x[0], reverse=True)

        winner = scored[0]
        alternatives = [
            {
                "value": str(s[2]),
                "sources": s[3],
                "score": round(s[0], 3),
            }
            for s in scored[1:]
        ]

        logger.info(
            "Conflict resolved for '%s': selected '%s' (score=%.3f) from %s — %s",
            field_name,
            winner[2],
            winner[0],
            winner[3],
            winner[1],
        )

        return ResolvedField(
            selected_value=winner[2],
            reason=winner[1],
            confidence=min(round(winner[0], 3), 1.0),
            sources=winner[3],
            alternatives=alternatives,
        )

    def _compute_score(
        self,
        group: list[dict[str, Any]],
        total_sources: int,
        total_unique_values: int,
    ) -> tuple[float, str]:
        """Compute the conflict resolution score for a value group.

        Score = SourceReliability × 0.35
              + AgreementBonus × 0.30
              + ExtractionConfidence × 0.25
              - ConflictPenalty × 0.10

        Args:
            group: List of candidates that agree on this value.
            total_sources: Total number of sources with conflicting values.
            total_unique_values: Number of distinct values.

        Returns:
            Tuple of (score, reason_string).
        """
        # Source reliability — max reliability among agreeing sources
        reliabilities = [
            Settings.SOURCE_RELIABILITY.get(c["source"], 0.5) for c in group
        ]
        source_reliability = max(reliabilities)

        # Agreement bonus — proportion of sources that agree
        agreement_ratio = len(group) / total_sources

        # Extraction confidence — average across agreeing sources
        extraction_confidences = [c.get("extraction_confidence", 0.5) for c in group]
        avg_extraction_conf = sum(extraction_confidences) / len(extraction_confidences)

        # Conflict penalty — more unique values = more uncertainty
        conflict_penalty = (total_unique_values - 1) / max(total_unique_values, 1)

        # Weighted score
        score = (
            source_reliability * Settings.CONFLICT_WEIGHT_SOURCE_RELIABILITY
            + agreement_ratio * Settings.CONFLICT_WEIGHT_AGREEMENT
            + avg_extraction_conf * Settings.CONFLICT_WEIGHT_EXTRACTION
            - conflict_penalty * Settings.CONFLICT_WEIGHT_PENALTY
        )

        # Build reason string
        sources = [c["source"] for c in group]
        reason_parts = []
        if len(group) > 1:
            reason_parts.append(f"{', '.join(sources)} agreed")
        else:
            reason_parts.append(f"Source: {sources[0]}")

        reason_parts.append(f"reliability={source_reliability:.2f}")
        reason_parts.append(f"agreement={agreement_ratio:.0%}")

        if conflict_penalty > 0:
            reason_parts.append(f"conflict_penalty={conflict_penalty:.2f}")

        reason = "; ".join(reason_parts)

        return score, reason

    @staticmethod
    def _normalize_value_key(value: Any) -> str:
        """Normalize a value for comparison purposes."""
        if isinstance(value, str):
            return value.strip().lower()
        return str(value).strip().lower()
