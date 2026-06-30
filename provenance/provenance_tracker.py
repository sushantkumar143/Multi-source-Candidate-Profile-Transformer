"""
Provenance Tracker.

Tracks the origin and transformation history of every field value
in the canonical profile. Every extracted value knows:
- Where it came from (source file)
- Which parser extracted it
- Which module modified it (normalization, conflict resolution)

Generates provenance entries as [{field, source, method}] for the
canonical profile.
"""

from __future__ import annotations

import logging
from typing import Any

from schemas.canonical import ProvenanceEntry

logger = logging.getLogger(__name__)


class ProvenanceTracker:
    """Tracks field-level provenance throughout the pipeline."""

    def __init__(self) -> None:
        self._entries: list[ProvenanceEntry] = []
        self._field_sources: dict[str, list[str]] = {}

    def track_extraction(
        self,
        field_name: str,
        source: str,
        method: str,
    ) -> None:
        """Record that a field was extracted from a source.

        Args:
            field_name: Canonical field name.
            source: Source identifier (e.g., "csv", "resume").
            method: Extraction method (e.g., "structured_parse", "regex_match").
        """
        self._entries.append(
            ProvenanceEntry(field=field_name, source=source, method=method)
        )
        if field_name not in self._field_sources:
            self._field_sources[field_name] = []
        if source not in self._field_sources[field_name]:
            self._field_sources[field_name].append(source)

    def track_transformation(
        self,
        field_name: str,
        method: str,
    ) -> None:
        """Record that a field was transformed by a pipeline stage.

        Args:
            field_name: Canonical field name.
            method: Transformation method (e.g., "phone_normalization", "conflict_resolution").
        """
        self._entries.append(
            ProvenanceEntry(field=field_name, source="pipeline", method=method)
        )

    def build_provenance(
        self,
        source_contributions: dict[str, list[str]],
        extraction_methods: dict[str, str],
        merge_log: list[dict[str, Any]],
    ) -> list[ProvenanceEntry]:
        """Build the final provenance list for the canonical profile.

        This is the main entry point, called after all pipeline stages.
        Combines extraction, transformation, and merge provenance.

        Args:
            source_contributions: {field: [sources]} from extraction.
            extraction_methods: {source: method} from parsers.
            merge_log: Merge decisions from the merge engine.

        Returns:
            List of ProvenanceEntry for the canonical profile.
        """
        entries: list[ProvenanceEntry] = []
        seen: set[str] = set()

        # Add extraction provenance
        for field_name, sources in source_contributions.items():
            for source in sources:
                method = extraction_methods.get(source, "unknown")
                key = f"{field_name}|{source}|{method}"
                if key not in seen:
                    seen.add(key)
                    entries.append(
                        ProvenanceEntry(
                            field=field_name,
                            source=source,
                            method=method,
                        )
                    )

        # Add merge/conflict resolution provenance
        for log_entry in merge_log:
            field_name = log_entry.get("field", "")
            action = log_entry.get("action", "")

            if action == "conflict_resolution":
                selected_source = log_entry.get("selected_source", "pipeline")
                key = f"{field_name}|{selected_source}|conflict_resolution"
                if key not in seen:
                    seen.add(key)
                    entries.append(
                        ProvenanceEntry(
                            field=field_name,
                            source=selected_source,
                            method="conflict_resolution",
                        )
                    )

        # Add any manually tracked entries
        for entry in self._entries:
            key = f"{entry.field}|{entry.source}|{entry.method}"
            if key not in seen:
                seen.add(key)
                entries.append(entry)

        logger.info("Built %d provenance entries", len(entries))
        return entries

    @property
    def field_sources(self) -> dict[str, list[str]]:
        """Get the source mapping for all tracked fields."""
        return dict(self._field_sources)
