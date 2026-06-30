"""
Canonical Candidate Profile schema.

This is the single source of truth in the pipeline.
All downstream modules (confidence, provenance, projection, validation)
operate exclusively on this model.

The canonical profile is NEVER modified by runtime configuration —
only the projected output changes.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Normalized location with ISO-3166 alpha-2 country code."""

    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = Field(
        default=None,
        description="ISO-3166 alpha-2 country code (e.g., 'US', 'IN')",
    )


class Links(BaseModel):
    """Collection of candidate profile links."""

    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    """A skill with confidence and source tracking.

    The assignment requires skills as [{name, confidence, sources[]}].
    """

    name: str = Field(..., description="Canonical skill name")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this skill attribution",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Sources that reported this skill",
    )


class Experience(BaseModel):
    """A single work experience entry.

    Dates are stored in YYYY-MM format as required by the assignment.
    """

    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = Field(
        default=None,
        description="Start date in YYYY-MM format",
    )
    end: Optional[str] = Field(
        default=None,
        description="End date in YYYY-MM format, or null if current",
    )
    summary: Optional[str] = None


class Education(BaseModel):
    """A single education entry."""

    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    start_year: Optional[int] = Field(
        default=None,
        description="Enrollment year",
    )
    end_year: Optional[int] = Field(
        default=None,
        description="Graduation year",
    )


class ProvenanceEntry(BaseModel):
    """Provenance tracking for a single field.

    Records where each value came from, which parser extracted it,
    and which method was used.
    """

    field: str = Field(..., description="Canonical field name")
    source: str = Field(
        ...,
        description="Source identifier (e.g., 'csv', 'resume', 'github')",
    )
    method: str = Field(
        ...,
        description="Extraction/derivation method (e.g., 'structured_parse', 'conflict_resolution')",
    )


class CanonicalProfile(BaseModel):
    """The canonical candidate profile — single source of truth.

    This model matches the assignment's default output schema exactly.
    All fields are populated by the pipeline stages (normalization, merging,
    confidence scoring, provenance tracking).
    """

    candidate_id: str = Field(
        ...,
        description="Unique candidate identifier (generated deterministically)",
    )
    full_name: str = Field(
        default="",
        description="Candidate's full name",
    )
    emails: list[str] = Field(
        default_factory=list,
        description="Deduplicated email addresses",
    )
    phones: list[str] = Field(
        default_factory=list,
        description="Phone numbers in E.164 format",
    )
    location: Optional[Location] = Field(
        default=None,
        description="Normalized location with ISO-3166 alpha-2 country",
    )
    links: Optional[Links] = Field(
        default=None,
        description="Profile links (LinkedIn, GitHub, portfolio, other)",
    )
    headline: Optional[str] = Field(
        default=None,
        description="Professional headline / tagline",
    )
    years_experience: Optional[float] = Field(
        default=None,
        description="Total years of professional experience",
    )
    skills: list[Skill] = Field(
        default_factory=list,
        description="Skills with confidence and source tracking",
    )
    experience: list[Experience] = Field(
        default_factory=list,
        description="Work experience entries with YYYY-MM dates",
    )
    education: list[Education] = Field(
        default_factory=list,
        description="Education entries",
    )
    provenance: list[ProvenanceEntry] = Field(
        default_factory=list,
        description="Field-level provenance tracking",
    )
    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall profile confidence score",
    )

    model_config = {"frozen": False, "extra": "forbid"}
