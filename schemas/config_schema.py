"""
Runtime Configuration schema.

Defines the config format the pipeline accepts to reshape output.
The config controls projection (field selection, renaming, normalization),
confidence inclusion, and missing-value policy.

The canonical profile is NEVER modified — only the projected output changes.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class FieldConfig(BaseModel):
    """Configuration for a single projected output field.

    Attributes:
        path: Output field name in the projected JSON.
        from_field: Canonical field path to read from (e.g., "emails[0]", "skills[].name").
                    If omitted, defaults to the same as `path`.
        type: Expected output type ("string", "string[]", "number", "object", etc.).
        normalize: Optional normalization to apply ("E164", "canonical", etc.).
        required: If true, the field must be present; behavior on missing depends on `on_missing`.
    """

    path: str = Field(..., description="Output field name")
    from_field: Optional[str] = Field(
        default=None,
        alias="from",
        description="Canonical field path to source from (e.g., 'emails[0]', 'skills[].name')",
    )
    type: str = Field(
        default="string",
        description="Expected output type: string, string[], number, object",
    )
    normalize: Optional[str] = Field(
        default=None,
        description="Normalization to apply: E164, canonical, etc.",
    )
    required: bool = Field(
        default=False,
        description="Whether this field is required in the output",
    )


class RuntimeConfig(BaseModel):
    """Runtime configuration for output projection.

    Controls which fields appear in the output, how they're named,
    whether confidence/provenance is included, and what happens with missing values.
    """

    fields: Optional[list[FieldConfig]] = Field(
        default=None,
        description="Field projection config. If null, all canonical fields are included.",
    )
    include_confidence: bool = Field(
        default=True,
        description="Whether to include confidence scores in output",
    )
    include_provenance: bool = Field(
        default=True,
        description="Whether to include provenance data in output",
    )
    on_missing: Literal["null", "omit", "error"] = Field(
        default="null",
        description="Policy for missing values: null (include as null), omit (exclude), error (raise)",
    )

    model_config = {"populate_by_name": True, "extra": "forbid"}
