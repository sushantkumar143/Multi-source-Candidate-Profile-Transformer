"""
Merge Engine.

Combines extracted data from multiple sources into a single merged record.
Supports:
- Semantic matching for deduplication (TF-IDF character n-gram cosine similarity)
- Normalization (company names, job titles, degrees, institutions)
- Data freshness (timestamp-based conflict weighting)
- Field-specific source reliability
"""

from __future__ import annotations

import logging
from typing import Any

from merger.conflict_resolver import ConflictResolver, ResolvedField
from merger.semantic_matcher import are_semantically_equivalent
from normalizers.semantic_normalizer import (
    normalize_company,
    normalize_title,
    normalize_degree,
    normalize_institution,
)
from config.settings import Settings

logger = logging.getLogger(__name__)


class MergeEngine:
    """Merges extracted data from multiple sources using semantic rules."""

    def __init__(self) -> None:
        self.conflict_resolver = ConflictResolver()
        self.conflicts: list[dict[str, Any]] = []
        self.merge_log: list[dict[str, Any]] = []

    def merge(
        self,
        source_data: list[tuple[str, dict[str, Any], float] | tuple[str, dict[str, Any], float, float]],
    ) -> dict[str, Any]:
        """Merge data from multiple sources.

        Args:
            source_data: List of tuples from each source.
                        Can be 3-tuples or 4-tuples with file modification timestamps.

        Returns:
            Merged dictionary with resolved values.
        """
        self.conflicts = []
        self.merge_log = []

        if not source_data:
            return {}

        # Collect all values for each field across sources
        field_values: dict[str, list[tuple[str, Any, float, float]]] = {}
        for item in source_data:
            if len(item) == 4:
                source_name, fields, confidence, timestamp = item
            else:
                source_name, fields, confidence = item
                timestamp = 0.0

            for field_name, value in fields.items():
                if field_name not in field_values:
                    field_values[field_name] = []
                field_values[field_name].append((source_name, value, confidence, timestamp))

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
        values: list[tuple[str, Any, float, float]],
    ) -> Any:
        """Merge values for a single field from multiple sources."""
        # Only one source has this field — no conflict
        if len(values) == 1:
            source, value, conf, ts = values[0]
            self.merge_log.append({
                "field": field_name,
                "action": "single_source",
                "source": source,
            })
            return value

        # List fields — union
        if field_name in ("emails", "phones", "skills"):
            return self._merge_list_field(field_name, values)

        # Structured list fields — concatenate & semantic deduplication
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
        values: list[tuple[str, Any, float, float]],
    ) -> list[Any]:
        """Merge list fields by taking the semantic union of all values."""
        merged: list[Any] = []
        for source, value, _, _ in values:
            items = value if isinstance(value, list) else [value]
            for item in items:
                # Deduplicate semantically
                exists = False
                for existing in merged:
                    if are_semantically_equivalent(str(item), str(existing), field_name):
                        exists = True
                        break
                if not exists:
                    merged.append(item)

        self.merge_log.append({
            "field": field_name,
            "action": "semantic_union",
            "sources": [s for s, _, _, _ in values],
            "count": len(merged),
        })
        return merged

    def _merge_structured_list(
        self,
        field_name: str,
        values: list[tuple[str, Any, float, float]],
    ) -> list[dict]:
        """Merge structured list fields (experience, education) semantically."""
        merged: list[dict] = []

        for source, value, conf, ts in values:
            items = value if isinstance(value, list) else [value]
            for item in items:
                if not isinstance(item, dict):
                    continue

                # Find if there is a semantically equivalent entry already merged
                match_idx = -1
                for idx, existing in enumerate(merged):
                    if field_name == "experience":
                        # Compare normalized company & job title
                        c1, c2 = normalize_company(item.get("company")), normalize_company(existing.get("company"))
                        t1, t2 = normalize_title(item.get("title")), normalize_title(existing.get("title"))
                        
                        comp_match = are_semantically_equivalent(c1, c2, "company")
                        title_match = are_semantically_equivalent(t1, t2, "title") if t1 and t2 else True
                        
                        if comp_match and title_match:
                            match_idx = idx
                            break
                            
                    elif field_name == "education":
                        # Compare normalized institution & degree
                        inst1, inst2 = normalize_institution(item.get("institution")), normalize_institution(existing.get("institution"))
                        deg1, deg2 = normalize_degree(item.get("degree")), normalize_degree(existing.get("degree"))
                        
                        inst_match = are_semantically_equivalent(inst1, inst2, "institution")
                        deg_match = are_semantically_equivalent(deg1, deg2, "degree") if deg1 and deg2 else True
                        
                        if inst_match and deg_match:
                            match_idx = idx
                            break

                if match_idx >= 0:
                    # Merge item into existing entry (resolving conflicts or keeping richer fields)
                    existing = merged[match_idx]
                    merged[match_idx] = self._merge_structured_entry(field_name, existing, item)
                else:
                    merged.append(item.copy())

        self.merge_log.append({
            "field": field_name,
            "action": "semantic_structured_merge",
            "sources": [s for s, _, _, _ in values],
            "count": len(merged),
        })
        return merged

    def _merge_structured_entry(self, field_name: str, existing: dict, new_item: dict) -> dict:
        """Merge two semantically matched dict entries (experience/education)."""
        merged_entry = existing.copy()
        
        # Merge basic fields: keep the one with longer/richer content
        for k, v in new_item.items():
            val_existing = existing.get(k)
            if val_existing is None:
                merged_entry[k] = v
            elif isinstance(v, str) and isinstance(val_existing, str):
                # If they are different, keep the longer description/detail
                if len(v) > len(val_existing):
                    merged_entry[k] = v
                    
        # Specially handle experience summary / bullets merging
        if field_name == "experience":
            sum_existing = existing.get("summary") or ""
            sum_new = new_item.get("summary") or ""
            if sum_new and sum_new not in sum_existing:
                # Deduplicate overlapping sentences if both summaries are text blocks
                # Simplistic merge: if they are different, append them cleanly
                if len(sum_new) > len(sum_existing):
                    merged_entry["summary"] = sum_new
                    
        return merged_entry

    def _merge_dict_field(
        self,
        field_name: str,
        values: list[tuple[str, Any, float, float]],
    ) -> dict:
        """Merge dict fields by deep-merging all values."""
        # Sort by source reliability (highest first)
        sorted_values = sorted(
            values,
            key=lambda x: Settings.SOURCE_RELIABILITY.get(x[0], 0.5),
            reverse=True,
        )

        merged: dict = {}
        for source, value, _, _ in sorted_values:
            if not isinstance(value, dict):
                continue
            for k, v in value.items():
                if k not in merged and v is not None:
                    merged[k] = v

        self.merge_log.append({
            "field": field_name,
            "action": "dict_merge",
            "sources": [s for s, _, _, _ in values],
        })
        return merged

    def _merge_scalar_field(
        self,
        field_name: str,
        values: list[tuple[str, Any, float, float]],
    ) -> Any:
        """Merge scalar fields using conflict resolution."""
        # Check if all values are the same
        unique_values: dict[str, list[tuple[str, float]]] = {}
        for source, value, confidence, timestamp in values:
            val_key = str(value).strip().lower() if isinstance(value, str) else str(value)
            if val_key not in unique_values:
                unique_values[val_key] = []
            unique_values[val_key].append((source, confidence))

        if len(unique_values) == 1:
            # All sources agree
            source, value, _, _ = values[0]
            self.merge_log.append({
                "field": field_name,
                "action": "agreement",
                "sources": [s for s, _, _, _ in values],
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
                    "timestamp": ts,
                }
                for source, value, conf, ts in values
            ],
        )

        self.conflicts.append({
            "field": field_name,
            "values": {source: str(value) for source, value, _, _ in values},
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
