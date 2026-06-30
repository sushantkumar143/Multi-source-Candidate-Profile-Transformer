"""
Projection Engine.

Reshapes the canonical profile into a configurable output format
based on the runtime config. Supports:
- Field selection: only include specified fields
- Field renaming: map canonical paths to custom output names
- Per-field normalization: apply normalizers based on config
- Missing value policy: null, omit, or error
- Confidence/provenance toggle

The canonical profile is NEVER modified — only the projected output changes.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from schemas.canonical import CanonicalProfile
from schemas.config_schema import RuntimeConfig, FieldConfig

logger = logging.getLogger(__name__)


class ProjectionEngine:
    """Projects canonical profiles into configurable output format."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.warnings: list[str] = []

    def project(self, profile: CanonicalProfile) -> dict[str, Any]:
        """Project a canonical profile into the configured output format.

        If no field config is provided, returns the full canonical profile.
        Otherwise, returns only the specified fields with renaming and
        normalization applied.

        Args:
            profile: The canonical profile to project.

        Returns:
            Projected output dictionary.
        """
        self.warnings = []
        profile_dict = profile.model_dump(mode="json")

        if self.config.fields is None:
            # No projection config — return full profile
            output = dict(profile_dict)
            if not self.config.include_confidence:
                output.pop("overall_confidence", None)
                # Remove confidence from skills
                if "skills" in output:
                    output["skills"] = [
                        {k: v for k, v in skill.items() if k != "confidence"}
                        for skill in output["skills"]
                    ]
            if not self.config.include_provenance:
                output.pop("provenance", None)
            return output

        # Apply field projections
        output: dict[str, Any] = {}
        for field_config in self.config.fields:
            value = self._resolve_field(field_config, profile_dict)
            output_key = field_config.path

            if value is None:
                value = self._handle_missing(field_config, output_key)
                if value is _OMIT:
                    continue

            output[output_key] = value

        # Add confidence if configured
        if self.config.include_confidence:
            output["overall_confidence"] = profile_dict.get("overall_confidence", 0.0)

        # Add provenance if configured
        if self.config.include_provenance:
            output["provenance"] = profile_dict.get("provenance", [])

        return output

    def _resolve_field(
        self,
        field_config: FieldConfig,
        profile_dict: dict[str, Any],
    ) -> Any:
        """Resolve a field value from the canonical profile.

        Supports path expressions like:
        - "full_name" → direct field access
        - "emails[0]" → first element of a list
        - "skills[].name" → pluck 'name' from each skill in the list
        - "location.city" → nested dict access

        Args:
            field_config: The field configuration.
            profile_dict: The canonical profile as a dict.

        Returns:
            The resolved value, or None if not found.
        """
        # Determine the source path
        source_path = field_config.from_field or field_config.path

        try:
            value = self._access_path(source_path, profile_dict)
        except (KeyError, IndexError, TypeError):
            logger.debug("Could not resolve path '%s'", source_path)
            return None

        # Apply normalization if configured
        if value is not None and field_config.normalize:
            value = self._apply_normalization(value, field_config.normalize)

        return value

    def _access_path(self, path: str, data: dict[str, Any]) -> Any:
        """Access a value using a dot/bracket path expression.

        Examples:
        - "full_name" → data["full_name"]
        - "emails[0]" → data["emails"][0]
        - "skills[].name" → [s["name"] for s in data["skills"]]
        - "location.city" → data["location"]["city"]
        """
        # Handle array pluck: "skills[].name"
        pluck_match = re.match(r"^(\w+)\[\]\.(\w+)$", path)
        if pluck_match:
            array_field = pluck_match.group(1)
            sub_field = pluck_match.group(2)
            array = data.get(array_field, [])
            if isinstance(array, list):
                return [
                    item.get(sub_field)
                    for item in array
                    if isinstance(item, dict) and sub_field in item
                ]
            return None

        # Handle indexed access: "emails[0]"
        index_match = re.match(r"^(\w+)\[(\d+)\]$", path)
        if index_match:
            field = index_match.group(1)
            index = int(index_match.group(2))
            array = data.get(field, [])
            if isinstance(array, list) and index < len(array):
                return array[index]
            return None

        # Handle dot notation: "location.city"
        if "." in path:
            parts = path.split(".")
            current = data
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
            return current

        # Simple field access
        return data.get(path)

    def _apply_normalization(self, value: Any, normalize: str) -> Any:
        """Apply a normalization to a value based on config.

        Supported normalizations:
        - "E164": Phone number to E.164 format
        - "canonical": Skill name to canonical form

        Args:
            value: The value to normalize.
            normalize: The normalization type.

        Returns:
            Normalized value.
        """
        if normalize.upper() == "E164":
            from normalizers.phone_normalizer import normalize_phone
            if isinstance(value, str):
                result, _ = normalize_phone(value)
                return result
            elif isinstance(value, list):
                return [normalize_phone(v)[0] for v in value if isinstance(v, str)]

        elif normalize.lower() == "canonical":
            from normalizers.skill_normalizer import normalize_skill
            if isinstance(value, str):
                result, _ = normalize_skill(value)
                return result
            elif isinstance(value, list):
                return [normalize_skill(v)[0] for v in value if isinstance(v, str)]

        return value

    def _handle_missing(
        self,
        field_config: FieldConfig,
        output_key: str,
    ) -> Any:
        """Handle a missing field value based on the on_missing policy.

        Args:
            field_config: The field configuration.
            output_key: The output key name (for error messages).

        Returns:
            None for "null", _OMIT for "omit", raises for "error".
        """
        policy = self.config.on_missing

        if field_config.required and policy == "error":
            msg = f"Required field '{output_key}' is missing"
            logger.error(msg)
            self.warnings.append(msg)
            # Still return None instead of crashing (graceful degradation)
            return None

        if policy == "omit":
            return _OMIT

        if field_config.required:
            self.warnings.append(f"Required field '{output_key}' is missing")

        return None


# Sentinel value for "omit this field"
_OMIT = object()
