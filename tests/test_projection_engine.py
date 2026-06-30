"""
Tests for the projection engine.

Covers:
- Default projection (all fields)
- Field selection
- Field renaming (from/path)
- Array indexing (emails[0])
- Array pluck (skills[].name)
- Dot notation (location.city)
- Missing value policies (null, omit)
- Confidence toggle
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from projector.projection_engine import ProjectionEngine
from schemas.canonical import (
    CanonicalProfile,
    Location,
    Links,
    Skill,
    Experience,
    Education,
    ProvenanceEntry,
)
from schemas.config_schema import RuntimeConfig, FieldConfig


def _sample_profile() -> CanonicalProfile:
    """Create a sample canonical profile for testing."""
    return CanonicalProfile(
        candidate_id="abc123",
        full_name="Priya Sharma",
        emails=["priya@email.com", "priya.s@work.com"],
        phones=["+919876543210"],
        location=Location(city="Bangalore", region="Karnataka", country="IN"),
        links=Links(
            linkedin="https://linkedin.com/in/priya",
            github="https://github.com/priya",
        ),
        headline="Software Engineer | Data Platform",
        years_experience=5.0,
        skills=[
            Skill(name="Python", confidence=0.9, sources=["csv", "linkedin"]),
            Skill(name="Spark", confidence=0.7, sources=["linkedin"]),
        ],
        experience=[
            Experience(
                company="Google", title="Senior SWE", start="2022-01", end=None, summary="ML pipelines"
            ),
        ],
        education=[
            Education(institution="IIT Delhi", degree="B.Tech", field="CS", end_year=2019),
        ],
        provenance=[
            ProvenanceEntry(field="full_name", source="csv", method="structured_parse"),
        ],
        overall_confidence=0.85,
    )


class TestProjectionEngine:
    """Tests for the projection engine."""

    def test_default_projection(self):
        """No config fields → return full profile."""
        config = RuntimeConfig()
        engine = ProjectionEngine(config)
        result = engine.project(_sample_profile())
        assert result["full_name"] == "Priya Sharma"
        assert result["overall_confidence"] == 0.85
        assert "provenance" in result

    def test_field_selection(self):
        """Only selected fields should appear in output."""
        config = RuntimeConfig(
            fields=[
                FieldConfig(path="full_name", type="string", required=True),
                FieldConfig(path="headline", type="string"),
            ],
            include_confidence=False,
            include_provenance=False,
        )
        engine = ProjectionEngine(config)
        result = engine.project(_sample_profile())
        assert "full_name" in result
        assert "headline" in result
        assert "emails" not in result
        assert "overall_confidence" not in result

    def test_field_renaming(self):
        """Fields with 'from' should be renamed in output."""
        config = RuntimeConfig(
            fields=[
                FieldConfig(path="primary_email", **{"from": "emails[0]"}, type="string"),
            ],
            include_confidence=False,
            include_provenance=False,
        )
        engine = ProjectionEngine(config)
        result = engine.project(_sample_profile())
        assert result["primary_email"] == "priya@email.com"

    def test_array_pluck(self):
        """skills[].name should extract skill names."""
        config = RuntimeConfig(
            fields=[
                FieldConfig(path="skills", **{"from": "skills[].name"}, type="string[]"),
            ],
            include_confidence=False,
            include_provenance=False,
        )
        engine = ProjectionEngine(config)
        result = engine.project(_sample_profile())
        assert result["skills"] == ["Python", "Spark"]

    def test_dot_notation(self):
        """location.city should access nested field."""
        config = RuntimeConfig(
            fields=[
                FieldConfig(path="city", **{"from": "location.city"}, type="string"),
            ],
            include_confidence=False,
            include_provenance=False,
        )
        engine = ProjectionEngine(config)
        result = engine.project(_sample_profile())
        assert result["city"] == "Bangalore"

    def test_on_missing_null(self):
        """Missing fields with on_missing=null should be null."""
        config = RuntimeConfig(
            fields=[
                FieldConfig(path="nonexistent", type="string"),
            ],
            on_missing="null",
            include_confidence=False,
            include_provenance=False,
        )
        engine = ProjectionEngine(config)
        result = engine.project(_sample_profile())
        assert result["nonexistent"] is None

    def test_on_missing_omit(self):
        """Missing fields with on_missing=omit should not appear."""
        config = RuntimeConfig(
            fields=[
                FieldConfig(path="nonexistent", type="string"),
                FieldConfig(path="full_name", type="string"),
            ],
            on_missing="omit",
            include_confidence=False,
            include_provenance=False,
        )
        engine = ProjectionEngine(config)
        result = engine.project(_sample_profile())
        assert "nonexistent" not in result
        assert result["full_name"] == "Priya Sharma"

    def test_confidence_toggle_off(self):
        """include_confidence=false should remove confidence."""
        config = RuntimeConfig(include_confidence=False)
        engine = ProjectionEngine(config)
        result = engine.project(_sample_profile())
        assert "overall_confidence" not in result

    def test_provenance_toggle_off(self):
        """include_provenance=false should remove provenance."""
        config = RuntimeConfig(include_provenance=False)
        engine = ProjectionEngine(config)
        result = engine.project(_sample_profile())
        assert "provenance" not in result
