"""
Conflict Resolver — intelligent scoring engine.

When multiple sources provide conflicting values for the same field,
this module uses a scoring formula to select the best value, factoring in:
- Field-specific source reliability
- Agreement bonus
- Extraction confidence
- Data freshness (timestamp)
- Conflict penalties
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
                - timestamp: file modification epoch float (optional)

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
            # Use field-specific reliability if available
            rel_dict = getattr(Settings, "FIELD_SOURCE_RELIABILITY", {})
            reliability = rel_dict.get(field_name, {}).get(c["source"], Settings.SOURCE_RELIABILITY.get(c["source"], 0.5))
            return ResolvedField(
                selected_value=c["value"],
                reason=f"Only source: {c['source']}",
                confidence=reliability,
                sources=[c["source"]],
            )

        # Find min/max timestamps for normalization
        timestamps = [c.get("timestamp", 0.0) for c in candidates if c.get("timestamp") is not None]
        min_ts = min(timestamps) if timestamps else 0.0
        max_ts = max(timestamps) if timestamps else 0.0

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
                field_name=field_name,
                group=group,
                total_sources=total_sources,
                total_unique_values=len(value_groups),
                min_ts=min_ts,
                max_ts=max_ts,
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
        field_name: str,
        group: list[dict[str, Any]],
        total_sources: int,
        total_unique_values: int,
        min_ts: float,
        max_ts: float,
    ) -> tuple[float, str]:
        """Compute the conflict resolution score for a value group."""
        # Field-specific Source reliability
        rel_dict = getattr(Settings, "FIELD_SOURCE_RELIABILITY", {})
        reliabilities = [
            rel_dict.get(field_name, {}).get(c["source"], Settings.SOURCE_RELIABILITY.get(c["source"], 0.5))
            for c in group
        ]
        source_reliability = max(reliabilities)

        # Agreement bonus
        agreement_ratio = len(group) / total_sources

        # Extraction confidence
        extraction_confidences = [c.get("extraction_confidence", 0.5) for c in group]
        avg_extraction_conf = sum(extraction_confidences) / len(extraction_confidences)

        # Freshness scoring (0.0 to 1.0)
        group_timestamps = [c.get("timestamp", 0.0) for c in group if c.get("timestamp") is not None]
        max_group_ts = max(group_timestamps) if group_timestamps else 0.0
        
        if max_ts - min_ts > 0:
            freshness = (max_group_ts - min_ts) / (max_ts - min_ts + 1e-5)
        else:
            freshness = 1.0

        # Conflict penalty
        conflict_penalty = (total_unique_values - 1) / max(total_unique_values, 1)

        # Load weights
        w_source = getattr(Settings, "CONFLICT_WEIGHT_SOURCE_RELIABILITY", 0.30)
        w_agree = getattr(Settings, "CONFLICT_WEIGHT_AGREEMENT", 0.25)
        w_extract = getattr(Settings, "CONFLICT_WEIGHT_EXTRACTION", 0.20)
        w_fresh = getattr(Settings, "CONFLICT_WEIGHT_FRESHNESS", 0.15)
        w_penalty = getattr(Settings, "CONFLICT_WEIGHT_PENALTY", 0.10)

        # Weighted score
        score = (
            source_reliability * w_source
            + agreement_ratio * w_agree
            + avg_extraction_conf * w_extract
            + freshness * w_fresh
            - conflict_penalty * w_penalty
        )

        # Build reason string
        sources = [c["source"] for c in group]
        reason_parts = []
        if len(group) > 1:
            reason_parts.append(f"{', '.join(sources)} agreed")
        else:
            reason_parts.append(f"Source: {sources[0]}")

        reason_parts.append(f"rel={source_reliability:.2f}")
        reason_parts.append(f"agree={agreement_ratio:.0%}")
        reason_parts.append(f"freshness={freshness:.2f}")

        if conflict_penalty > 0:
            reason_parts.append(f"penalty={conflict_penalty:.2f}")

        reason = "; ".join(reason_parts)

        return score, reason

    @staticmethod
    def _normalize_value_key(value: Any) -> str:
        """Normalize a value for comparison purposes."""
        if isinstance(value, str):
            return value.strip().lower()
        return str(value).strip().lower()
