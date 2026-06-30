"""
Extracted Record schema.

Represents raw data extracted from any single source parser.
This is the common interchange format between parsers and the rest of the pipeline.
Every parser must produce ExtractedRecord instances.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractedRecord(BaseModel):
    """Raw extracted data from a single source.

    Attributes:
        source: Source identifier (e.g., "csv", "resume", "github", "linkedin", "recruiter_notes").
        source_file: Filename or path of the source file.
        raw_fields: Raw key-value pairs as extracted by the parser.
                    Keys should attempt to match canonical field names where possible.
        extraction_method: How data was extracted (e.g., "structured_parse",
                          "pdf_text_extract", "regex_match", "json_parse").
        extraction_confidence: Parser-assigned confidence in the quality of extraction (0.0–1.0).
    """

    source: str = Field(
        ...,
        description="Source identifier: csv, resume, github, linkedin, recruiter_notes",
    )
    source_file: str = Field(
        ...,
        description="Filename or path of the source file",
    )
    raw_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw key-value pairs as extracted by the parser",
    )
    extraction_method: str = Field(
        ...,
        description="Method used for extraction: structured_parse, pdf_text_extract, regex_match, json_parse",
    )
    extraction_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Parser-assigned confidence in extraction quality (0.0-1.0)",
    )

    model_config = {"frozen": False, "extra": "forbid"}
