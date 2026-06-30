"""
Merge Engine.

Combines extracted data from multiple sources into a single merged record.
Handles:
- Duplicate values (union of lists)
- Conflicting values (delegates to ConflictResolver)
- Missing values (one source has it, others don't — straightforward)

This is the core of the multi-source merge logic.
"""

from __future__ import annotations

import logging
from typing import Any

from merger.conflict_resolver import ConflictResolver, ResolvedField
from schemas.extracted import ExtractedRecord

logger = logging.getLogger(__name__)


class MergeEngine:
    """Merges extracted data from multiple sources.

    Takes a list of (source_name, extracted_fields) pairs and
    produces a single merged record with conflict resolution metadata.
    """

    def __init__(self) -> None:
        self.conflict_resolver = ConflictResolver()
        self.conflicts: list[dict[str, Any]] = []
        self.merge_log: list[dict[str, Any]] = []

    def merge(
        self,
        source_data: list[tuple[str, dict[str, Any], float]],
    ) -> dict[str, Any]:
        """Merge data from multiple sources.

        Args:
            source_data: List of (source_name, extracted_fields, extraction_confidence)
                        tuples from each source.

        Returns:
            Merged dictionary with resolved values.
        """
        self.conflicts = []
        self.merge_log = []

        if not source_data:
            return {}

        # Collect all values for each field across sources
        field_values: dict[str, list[tuple[str, Any, float]]] = {}
        for source_name, fields, confidence in source_data:
            for field_name, value in fields.items():
                if field_name not in field_values:
                    field_values[field_name] = []
                field_values[field_name].append((source_name, value, confidence))

        # Merge each field
        merged: dict[str, Any] = {}
        for field_name, values in field_values.items():
            merged_value = self._merge_field(field_name, values)
            if merged_value is not None:
                merged[field_name] = merged_value

        logger.info(
            "Merged %d fields from %d sources, %d conflicts resolved",
            len(merged),
            len(source_data),
            len(self.conflicts),
        )

        return merged

    def _merge_field(
        self,
        field_name: str,
        values: list[tuple[str, Any, float]],
    ) -> Any:
        """Merge values for a single field from multiple sources.

        Strategy:
        - List fields (emails, phones, skills): union of all values
        - Structured list fields (experience, education): concatenate and dedup
        - Dict fields (links, location): deep merge
        - Scalar fields: conflict resolution if values differ

        Args:
            field_name: The canonical field name.
            values: List of (source_name, value, extraction_confidence) tuples.

        Returns:
            The merged value.
        """
        # Only one source has this field — no conflict
        if len(values) == 1:
            source, value, conf = values[0]
            self.merge_log.append({
                "field": field_name,
                "action": "single_source",
                "source": source,
            })
            return value

        # List fields — union
        if field_name in ("emails", "phones", "skills"):
            return self._merge_list_field(field_name, values)

        # Structured list fields — concatenate
        if field_name in ("experience", "education"):
            return self._merge_structured_list(field_name, values)

        # Dict fields — deep merge
        if field_name in ("links", "location"):
            return self._merge_dict_field(field_name, values)

        # Scalar fields — conflict resolution
        return self._merge_scalar_field(field_name, values)

    def _merge_list_field(
        self,
        field_name: str,
        values: list[tuple[str, Any, float]],
    ) -> list[Any]:
        """Merge list fields by taking the union of all values."""
        merged: list[Any] = []
        seen: set[str] = set()

        for source, value, _ in values:
            items = value if isinstance(value, list) else [value]
            for item in items:
                key = str(item).lower() if isinstance(item, str) else str(item)
                if key not in seen:
                    seen.add(key)
                    merged.append(item)

        self.merge_log.append({
            "field": field_name,
            "action": "union",
            "sources": [s for s, _, _ in values],
            "count": len(merged),
        })
        return merged

    def _merge_structured_list(
        self,
        field_name: str,
        values: list[tuple[str, Any, float]],
    ) -> list[dict]:
        """Merge structured list fields (experience, education).

        Concatenates all entries, attempting to dedup based on key fields.
        """
        merged: list[dict] = []
        seen_keys: set[str] = set()

        for source, value, _ in values:
            items = value if isinstance(value, list) else [value]
            for item in items:
                if not isinstance(item, dict):
                    continue

                # Create a dedup key from key fields
                if field_name == "experience":
                    key = f"{item.get('company', '')}|{item.get('title', '')}".lower()
                elif field_name == "education":
                    key = f"{item.get('institution', '')}|{item.get('degree', '')}".lower()
                else:
                    key = str(item)

                if key not in seen_keys and key != "|":
                    seen_keys.add(key)
                    merged.append(item)

        self.merge_log.append({
            "field": field_name,
            "action": "structured_merge",
            "sources": [s for s, _, _ in values],
            "count": len(merged),
        })
        return merged

    def _merge_dict_field(
        self,
        field_name: str,
        values: list[tuple[str, Any, float]],
    ) -> dict:
        """Merge dict fields by deep-merging all values.

        Later sources can fill in missing keys but don't overwrite existing ones
        from higher-reliability sources.
        """
        # Sort by source reliability (highest first)
        from config.settings import Settings

        sorted_values = sorted(
            values,
            key=lambda x: Settings.SOURCE_RELIABILITY.get(x[0], 0.5),
            reverse=True,
        )

        merged: dict = {}
        for source, value, _ in sorted_values:
            if not isinstance(value, dict):
                continue
            for k, v in value.items():
                if k not in merged and v is not None:
                    merged[k] = v

        self.merge_log.append({
            "field": field_name,
            "action": "dict_merge",
            "sources": [s for s, _, _ in values],
        })
        return merged

    def _merge_scalar_field(
        self,
        field_name: str,
        values: list[tuple[str, Any, float]],
    ) -> Any:
        """Merge scalar fields using conflict resolution.

        If all sources agree, returns the common value.
        If sources disagree, uses the ConflictResolver to pick the best value.
        """
        # Check if all values are the same
        unique_values: dict[str, list[tuple[str, float]]] = {}
        for source, value, confidence in values:
            val_key = str(value).strip().lower() if isinstance(value, str) else str(value)
            if val_key not in unique_values:
                unique_values[val_key] = []
            unique_values[val_key].append((source, confidence))

        if len(unique_values) == 1:
            # All sources agree
            source, value, _ = values[0]
            self.merge_log.append({
                "field": field_name,
                "action": "agreement",
                "sources": [s for s, _, _ in values],
                "value": str(value),
            })
            return value

        # Conflict — use resolver
        resolved: ResolvedField = self.conflict_resolver.resolve(
            field_name=field_name,
            candidates=[
                {
                    "source": source,
                    "value": value,
                    "extraction_confidence": conf,
                }
                for source, value, conf in values
            ],
        )

        self.conflicts.append({
            "field": field_name,
            "values": {source: str(value) for source, value, _ in values},
            "selected": str(resolved.selected_value),
            "reason": resolved.reason,
            "confidence": resolved.confidence,
        })

        self.merge_log.append({
            "field": field_name,
            "action": "conflict_resolution",
            "selected_source": resolved.sources[0] if resolved.sources else "unknown",
            "reason": resolved.reason,
        })

        return resolved.selected_value
