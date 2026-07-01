"""
Tests for the merge engine and conflict resolver.

Covers:
- Single source merge (no conflicts)
- Multi-source agreement
- Multi-source conflict (scoring-based resolution)
- List field union
- Dict field deep merge
- Edge cases (empty inputs)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from merger.merge_engine import MergeEngine
from merger.conflict_resolver import ConflictResolver


class TestMergeEngine:
    """Tests for the merge engine."""

    def test_single_source(self):
        """Single source should pass through without conflicts."""
        engine = MergeEngine()
        data = [
            ("csv", {"full_name": "Priya Sharma", "emails": ["priya@email.com"]}, 0.9),
        ]
        merged = engine.merge(data)
        assert merged["full_name"] == "Priya Sharma"
        assert merged["emails"] == ["priya@email.com"]
        assert len(engine.conflicts) == 0

    def test_agreement_across_sources(self):
        """When sources agree, no conflict should be recorded."""
        engine = MergeEngine()
        data = [
            ("csv", {"full_name": "Priya Sharma"}, 0.9),
            ("linkedin", {"full_name": "Priya Sharma"}, 0.75),
        ]
        merged = engine.merge(data)
        assert merged["full_name"] == "Priya Sharma"
        assert len(engine.conflicts) == 0

    def test_conflict_resolution(self):
        """When sources conflict, resolver should pick the best value."""
        engine = MergeEngine()
        data = [
            ("csv", {"current_company": "Amazon"}, 0.9),
            ("linkedin", {"current_company": "Google"}, 0.75),
            ("recruiter_notes", {"current_company": "Google"}, 0.5),
        ]
        merged = engine.merge(data)
        # LinkedIn + Recruiter Notes agree on Google; CSV says Amazon
        # Google should win due to agreement bonus
        assert merged["current_company"] == "Google"
        assert len(engine.conflicts) == 1

    def test_list_field_union(self):
        """List fields should be unioned across sources."""
        engine = MergeEngine()
        data = [
            ("csv", {"skills": ["Python", "Java"]}, 0.9),
            ("linkedin", {"skills": ["Python", "Spark"]}, 0.75),
        ]
        merged = engine.merge(data)
        assert "Python" in merged["skills"]
        assert "Java" in merged["skills"]
        assert "Spark" in merged["skills"]

    def test_dict_field_merge(self):
        """Dict fields should deep-merge (fill in missing keys)."""
        engine = MergeEngine()
        data = [
            ("csv", {"links": {"linkedin": "https://linkedin.com/in/priya"}}, 0.9),
            ("github", {"links": {"github": "https://github.com/priya"}}, 0.8),
        ]
        merged = engine.merge(data)
        assert "linkedin" in merged["links"]
        assert "github" in merged["links"]

    def test_empty_input(self):
        """Empty input should return empty dict."""
        engine = MergeEngine()
        merged = engine.merge([])
        assert merged == {}


class TestConflictResolver:
    """Tests for the conflict resolver."""

    def test_single_candidate(self):
        """Single candidate should be selected directly."""
        resolver = ConflictResolver()
        result = resolver.resolve(
            field_name="title",
            candidates=[
                {"source": "csv", "value": "Software Engineer", "extraction_confidence": 0.9},
            ],
        )
        assert result.selected_value == "Software Engineer"
        assert result.confidence > 0

    def test_agreement_boosts_score(self):
        """Values supported by more sources should win."""
        resolver = ConflictResolver()
        result = resolver.resolve(
            field_name="current_company",
            candidates=[
                {"source": "csv", "value": "Amazon", "extraction_confidence": 0.9},
                {"source": "linkedin", "value": "Google", "extraction_confidence": 0.75},
                {"source": "recruiter_notes", "value": "Google", "extraction_confidence": 0.5},
            ],
        )
        # Google has 2/3 agreement
        assert result.selected_value == "Google"
        assert "agreed" in result.reason.lower() or "agreement" in result.reason.lower()

    def test_high_reliability_wins_over_agreement_when_close(self):
        """Higher reliability source should win when agreement is equal."""
        resolver = ConflictResolver()
        result = resolver.resolve(
            field_name="title",
            candidates=[
                {"source": "csv", "value": "SDE", "extraction_confidence": 0.9},
                {"source": "recruiter_notes", "value": "Engineer", "extraction_confidence": 0.3},
            ],
        )
        # CSV has higher reliability (0.8) vs recruiter_notes (0.5)
        assert result.selected_value == "SDE"

    def test_alternatives_tracked(self):
        """Rejected values should be tracked as alternatives."""
        resolver = ConflictResolver()
        result = resolver.resolve(
            field_name="company",
            candidates=[
                {"source": "csv", "value": "Amazon", "extraction_confidence": 0.9},
                {"source": "linkedin", "value": "Google", "extraction_confidence": 0.75},
            ],
        )
        assert len(result.alternatives) == 1
        alt = result.alternatives[0]
        assert "score" in alt

    def test_semantic_match_dedup(self):
        """Test that company names like 'Google LLC' and 'Google' are matched semantically and deduplicated."""
        engine = MergeEngine()
        data = [
            ("resume", {"experience": [{"company": "Google LLC", "title": "SWE", "start": "2020-01", "end": "2021-01"}]}, 0.8),
            ("linkedin", {"experience": [{"company": "Google", "title": "Software Engineer", "start": "2020-01", "end": "2021-01"}]}, 0.8),
        ]
        merged = engine.merge(data)
        # They should be merged into a single entry
        assert len(merged["experience"]) == 1
        assert merged["experience"][0]["company"] == "Google LLC"  # kept because resume is more reliable for experience

    def test_field_specific_reliability(self):
        """Test that skills prioritize GitHub source even if another source has higher general reliability."""
        resolver = ConflictResolver()
        result = resolver.resolve(
            field_name="skills",
            candidates=[
                {"source": "csv", "value": "Java", "extraction_confidence": 0.8},
                {"source": "github", "value": "Python", "extraction_confidence": 0.8},
            ],
        )
        # For skills, github reliability is 0.90, csv is 0.70.
        # Although csv is generally 0.80 and github is 0.75 in Settings.SOURCE_RELIABILITY,
        # the field-specific reliability mapping must override it!
        assert result.selected_value == "Python"

    def test_freshness_scoring(self):
        """Test that fresher source values win in conflict resolution."""
        resolver = ConflictResolver()
        result = resolver.resolve(
            field_name="title",
            candidates=[
                {"source": "csv", "value": "Junior Developer", "extraction_confidence": 0.9, "timestamp": 1000.0},
                {"source": "resume", "value": "Senior Developer", "extraction_confidence": 0.9, "timestamp": 2000.0},
            ],
        )
        # Resume has higher timestamp (fresher), so it should win
        assert result.selected_value == "Senior Developer"
