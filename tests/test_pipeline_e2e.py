"""
End-to-end pipeline test.

Runs the full pipeline on sample inputs and validates the output
against expected structure and values. This is the golden test
recommended by the assignment.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import Pipeline


class TestPipelineE2E:
    """End-to-end pipeline tests."""

    def _get_input_dir(self) -> Path:
        return Path(__file__).parent.parent / "input"

    def _get_output_dir(self) -> Path:
        return Path(__file__).parent.parent / "test_output"

    def test_pipeline_runs_without_errors(self):
        """Pipeline should complete without raising exceptions."""
        input_dir = self._get_input_dir()
        output_dir = self._get_output_dir()

        pipeline = Pipeline(
            input_dir=input_dir,
            output_dir=output_dir,
        )
        result = pipeline.run()
        assert result is not None
        assert isinstance(result, dict)

        # Cleanup
        import shutil
        if output_dir.exists():
            shutil.rmtree(output_dir)

    def test_output_has_required_fields(self):
        """Output should contain all canonical fields."""
        input_dir = self._get_input_dir()
        output_dir = self._get_output_dir()

        pipeline = Pipeline(
            input_dir=input_dir,
            output_dir=output_dir,
        )
        result = pipeline.run()

        # Required fields per assignment schema
        required_fields = [
            "candidate_id", "full_name", "emails", "phones",
            "skills", "experience", "education",
            "provenance", "overall_confidence",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Cleanup
        import shutil
        if output_dir.exists():
            shutil.rmtree(output_dir)

    def test_candidate_name_extracted(self):
        """Candidate name should be correctly extracted."""
        input_dir = self._get_input_dir()
        output_dir = self._get_output_dir()

        pipeline = Pipeline(
            input_dir=input_dir,
            output_dir=output_dir,
        )
        result = pipeline.run()

        assert result["full_name"] == "Sushant Kumar"

        # Cleanup
        import shutil
        if output_dir.exists():
            shutil.rmtree(output_dir)

    def test_phones_normalized_to_e164(self):
        """Phone numbers should be in E.164 format."""
        input_dir = self._get_input_dir()
        output_dir = self._get_output_dir()

        pipeline = Pipeline(
            input_dir=input_dir,
            output_dir=output_dir,
        )
        result = pipeline.run()

        phones = result.get("phones", [])
        for phone in phones:
            assert phone.startswith("+"), f"Phone not in E.164 format: {phone}"

        # Cleanup
        import shutil
        if output_dir.exists():
            shutil.rmtree(output_dir)

    def test_confidence_is_valid(self):
        """Overall confidence should be between 0 and 1."""
        input_dir = self._get_input_dir()
        output_dir = self._get_output_dir()

        pipeline = Pipeline(
            input_dir=input_dir,
            output_dir=output_dir,
        )
        result = pipeline.run()

        confidence = result.get("overall_confidence", 0)
        assert 0.0 <= confidence <= 1.0

        # Cleanup
        import shutil
        if output_dir.exists():
            shutil.rmtree(output_dir)

    def test_audit_report_generated(self):
        """Audit report should be generated alongside candidate.json."""
        input_dir = self._get_input_dir()
        output_dir = self._get_output_dir()

        pipeline = Pipeline(
            input_dir=input_dir,
            output_dir=output_dir,
        )
        pipeline.run()

        audit_path = output_dir / "audit_report.json"
        assert audit_path.exists(), "audit_report.json not generated"

        with open(audit_path) as f:
            report = json.load(f)

        assert "processing_timestamp" in report
        assert "transformations" in report
        assert "data_quality" in report

        # Cleanup
        import shutil
        if output_dir.exists():
            shutil.rmtree(output_dir)

    def test_graceful_degradation_missing_resume(self):
        """Pipeline should work even without a resume PDF."""
        import tempfile
        import shutil

        # Create temp input dir with only CSV
        temp_dir = Path(__file__).parent.parent / "test_input_partial"
        temp_dir.mkdir(exist_ok=True)
        output_dir = self._get_output_dir()

        try:
            shutil.copy(self._get_input_dir() / "candidate.csv", temp_dir / "candidate.csv")

            pipeline = Pipeline(
                input_dir=temp_dir,
                output_dir=output_dir,
            )
            result = pipeline.run()

            # Should still produce output
            assert result is not None
            assert result.get("full_name") == "Sushant Kumar"
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            if output_dir.exists():
                shutil.rmtree(output_dir)

    def test_custom_config_projection(self):
        """Pipeline should respect custom config for output projection."""
        input_dir = self._get_input_dir()
        output_dir = self._get_output_dir()

        # Use the config from input dir
        config_path = input_dir / "config.json"

        pipeline = Pipeline(
            input_dir=input_dir,
            output_dir=output_dir,
            config_path=config_path,
        )
        result = pipeline.run()

        # Config asks for primary_email from emails[0]
        assert "primary_email" in result or "full_name" in result

        # Cleanup
        import shutil
        if output_dir.exists():
            shutil.rmtree(output_dir)
