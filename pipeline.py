"""
Pipeline Orchestrator.

Wires together all pipeline stages in the correct order:
1. Source Detection → Parse all input files
2. Field Extraction → Map raw fields to canonical names
3. Normalization → Phones, dates, skills, location, dedup
4. Merging → Combine data from multiple sources, resolve conflicts
5. Confidence Scoring → Compute per-field and overall confidence
6. Provenance Tracking → Build provenance entries
7. Projection → Apply runtime config to reshape output
8. Validation → Validate the final output
9. Output → Write candidate.json + audit_report.json

This is the only file that knows about all pipeline stages.
Each stage is independently testable.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from audit.audit_engine import AuditEngine
from confidence.confidence_engine import ConfidenceEngine
from config.loader import load_config
from extractors.field_extractor import extract_fields
from merger.merge_engine import MergeEngine
from normalizers.date_normalizer import normalize_date, normalize_dates_in_experience
from normalizers.deduplicator import deduplicate_emails, deduplicate_phones, deduplicate_skills
from normalizers.location_normalizer import normalize_location
from normalizers.phone_normalizer import normalize_phones
from normalizers.skill_normalizer import normalize_skills
from parsers.registry import create_default_registry
from projector.projection_engine import ProjectionEngine
from provenance.provenance_tracker import ProvenanceTracker
from schemas.canonical import (
    CanonicalProfile,
    Education,
    Experience,
    Links,
    Location,
    Skill,
)
from schemas.config_schema import RuntimeConfig
from schemas.extracted import ExtractedRecord
from utils.helpers import generate_candidate_id, clean_string
from validator.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


class Pipeline:
    """Main pipeline orchestrator."""

    def __init__(self, input_dir: Path, output_dir: Path, config_path: Path | None = None) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.config_path = config_path
        self.audit = AuditEngine()

    def run(self) -> dict[str, Any]:
        """Execute the full pipeline.

        Returns:
            The final output dictionary (candidate.json content).
        """
        self.audit.start()
        logger.info("=" * 60)
        logger.info("PIPELINE START")
        logger.info("Input: %s", self.input_dir)
        logger.info("Output: %s", self.output_dir)
        logger.info("=" * 60)

        # -- Stage 1: Source Detection & Parsing --
        logger.info("--- Stage 1: Source Detection & Parsing ---")
        registry = create_default_registry()
        records: list[ExtractedRecord] = registry.detect_and_parse(self.input_dir)

        if not records:
            logger.error("No data extracted from any source -- aborting")
            self.audit.add_error("No data extracted from any source")
            self._write_audit({}, {})
            return {}

        self.audit.set_sources([r.source_file for r in records])
        logger.info("Parsed %d source(s): %s", len(records), [r.source for r in records])

        # -- Stage 2: Field Extraction --
        logger.info("--- Stage 2: Field Extraction ---")
        extracted_data: list[tuple[str, dict[str, Any], float, float]] = []
        extraction_methods: dict[str, str] = {}

        for record in records:
            fields = extract_fields(record)
            file_path = self.input_dir / record.source_file
            timestamp = file_path.stat().st_mtime if file_path.exists() else 0.0
            extracted_data.append((record.source, fields, record.extraction_confidence, timestamp))
            extraction_methods[record.source] = record.extraction_method
            logger.info(
                "Extracted %d fields from %s (%s)",
                len(fields), record.source_file, record.source,
            )

        # -- Stage 3: Normalization --
        logger.info("--- Stage 3: Normalization ---")
        all_transformations: list[dict[str, str]] = []
        all_duplicates: list[dict[str, str]] = []
        normalization_results: dict[str, bool] = {}

        for i, item in enumerate(extracted_data):
            source = item[0]
            fields = item[1]
            conf = item[2]
            timestamp = item[3]

            # Normalize phones
            if "phones" in fields and isinstance(fields["phones"], list):
                norm_phones, phone_transforms = normalize_phones(fields["phones"])
                fields["phones"] = norm_phones
                all_transformations.extend(phone_transforms)
                normalization_results["phones"] = all(
                    t.get("success") == "True" for t in phone_transforms
                ) if phone_transforms else True

            # Normalize skills
            if "skills" in fields and isinstance(fields["skills"], list):
                norm_skills, skill_transforms = normalize_skills(fields["skills"])
                fields["skills"] = norm_skills
                all_transformations.extend(skill_transforms)
                normalization_results["skills"] = True

            # Normalize experience dates
            if "experience" in fields and isinstance(fields["experience"], list):
                norm_exp, exp_transforms = normalize_dates_in_experience(fields["experience"])
                fields["experience"] = norm_exp
                all_transformations.extend(exp_transforms)
                normalization_results["experience"] = True

            # Normalize location
            if "location" in fields:
                loc_data, loc_transforms = normalize_location(fields["location"])
                fields["location"] = loc_data
                all_transformations.extend(loc_transforms)
                normalization_results["location"] = True

            extracted_data[i] = (source, fields, conf, timestamp)

        self.audit.add_transformations(all_transformations)
        logger.info("Applied %d normalizations", len(all_transformations))

        # -- Stage 4: Merging + Conflict Resolution --
        logger.info("--- Stage 4: Merging + Conflict Resolution ---")
        merger = MergeEngine()
        merged = merger.merge(extracted_data)

        self.audit.add_conflicts(merger.conflicts)
        if merger.conflicts:
            logger.info("Resolved %d conflicts", len(merger.conflicts))

        # -- Stage 4b: Post-merge deduplication --
        if "emails" in merged and isinstance(merged["emails"], list):
            merged["emails"], email_dupes = deduplicate_emails(merged["emails"])
            all_duplicates.extend(email_dupes)

        if "phones" in merged and isinstance(merged["phones"], list):
            merged["phones"], phone_dupes = deduplicate_phones(merged["phones"])
            all_duplicates.extend(phone_dupes)

        if "skills" in merged and isinstance(merged["skills"], list):
            merged["skills"], skill_dupes = deduplicate_skills(merged["skills"])
            all_duplicates.extend(skill_dupes)

        self.audit.add_duplicates(all_duplicates)
        if all_duplicates:
            logger.info("Removed %d duplicates", len(all_duplicates))

        # -- Stage 5: Build Canonical Profile --
        logger.info("--- Stage 5: Building Canonical Profile ---")

        # Track source contributions
        source_contributions: dict[str, list[str]] = {}
        for item in extracted_data:
            source = item[0]
            fields = item[1]
            for field_name in fields:
                if field_name not in source_contributions:
                    source_contributions[field_name] = []
                if source not in source_contributions[field_name]:
                    source_contributions[field_name].append(source)

        profile = self._build_canonical_profile(merged, source_contributions)

        # -- Stage 6: Confidence Engine --
        logger.info("--- Stage 6: Confidence Scoring ---")
        confidence_engine = ConfidenceEngine()
        extraction_confidences = {r.source: r.extraction_confidence for r in records}

        field_confidences, overall_confidence = confidence_engine.compute(
            merged_data=merged,
            source_contributions=source_contributions,
            normalization_results=normalization_results,
            conflicts=merger.conflicts,
            extraction_confidences=extraction_confidences,
        )

        profile.overall_confidence = overall_confidence

        # Update skill confidences
        for skill in profile.skills:
            skill.confidence = field_confidences.get("skills", 0.5)

        # -- Stage 7: Provenance --
        logger.info("--- Stage 7: Provenance Tracking ---")
        provenance_tracker = ProvenanceTracker()
        profile.provenance = provenance_tracker.build_provenance(
            source_contributions=source_contributions,
            extraction_methods=extraction_methods,
            merge_log=merger.merge_log,
        )

        # -- Stage 8: Projection --
        logger.info("--- Stage 8: Projection ---")
        config = load_config(self.config_path)
        projector = ProjectionEngine(config)
        output = projector.project(profile)

        if projector.warnings:
            for w in projector.warnings:
                self.audit.add_warning(w)

        # -- Stage 9: Validation --
        logger.info("--- Stage 9: Validation ---")
        validator = SchemaValidator()
        is_projected = config.fields is not None
        is_valid = validator.validate(output, is_projected=is_projected)

        if not is_valid:
            for error in validator.errors:
                self.audit.add_error(error)

        for warning in validator.warnings:
            self.audit.add_warning(warning)

        # -- Stage 10: Output --
        logger.info("--- Stage 10: Writing Output ---")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Write candidate.json
        candidate_path = self.output_dir / "candidate.json"
        with open(candidate_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Written: %s", candidate_path)

        # Write candidate_full.json (complete, unprojected profile for testing)
        candidate_full_path = self.output_dir / "candidate_full.json"
        with open(candidate_full_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        logger.info("Written: %s", candidate_full_path)

        # Write audit report
        self._write_audit(profile.model_dump(), field_confidences)

        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("Overall Confidence: %.3f", overall_confidence)
        logger.info("=" * 60)

        return output

    def _build_canonical_profile(
        self,
        merged: dict[str, Any],
        source_contributions: dict[str, list[str]],
    ) -> CanonicalProfile:
        """Build a CanonicalProfile from merged data.

        Args:
            merged: Merged field data from all sources.
            source_contributions: Which sources contributed each field.

        Returns:
            Populated CanonicalProfile instance.
        """
        # Generate deterministic candidate ID
        name = clean_string(merged.get("full_name", "")) or ""
        emails = merged.get("emails", [])
        first_email = emails[0] if emails else ""
        candidate_id = generate_candidate_id(name, first_email)

        # Build location
        location = None
        loc_data = merged.get("location")
        if isinstance(loc_data, dict):
            location = Location(**{
                k: v for k, v in loc_data.items()
                if k in ("city", "region", "country")
            })
        elif isinstance(loc_data, str):
            from normalizers.location_normalizer import normalize_location as norm_loc
            loc_dict, _ = norm_loc(loc_data)
            location = Location(**loc_dict)

        # Build links
        links = None
        links_data = merged.get("links")
        if isinstance(links_data, dict):
            links = Links(
                linkedin=links_data.get("linkedin"),
                github=links_data.get("github"),
                portfolio=links_data.get("portfolio"),
                other=links_data.get("other", []),
            )

        # Build skills with source tracking
        skills: list[Skill] = []
        raw_skills = merged.get("skills", [])
        if isinstance(raw_skills, list):
            skill_sources = source_contributions.get("skills", [])
            for skill_name in raw_skills:
                if isinstance(skill_name, str):
                    skills.append(Skill(
                        name=skill_name,
                        confidence=0.0,  # Will be set by confidence engine
                        sources=skill_sources,
                    ))

        # Build experience
        experience: list[Experience] = []
        raw_exp = merged.get("experience", [])
        if isinstance(raw_exp, list):
            for entry in raw_exp:
                if isinstance(entry, dict):
                    experience.append(Experience(
                        company=clean_string(entry.get("company")),
                        title=clean_string(entry.get("title")),
                        start=entry.get("start"),
                        end=entry.get("end"),
                        summary=clean_string(entry.get("summary")),
                    ))

        # Build education
        education: list[Education] = []
        raw_edu = merged.get("education", [])
        if isinstance(raw_edu, list):
            for entry in raw_edu:
                if isinstance(entry, dict):
                    education.append(Education(
                        institution=clean_string(entry.get("institution")),
                        degree=clean_string(entry.get("degree")),
                        field=clean_string(entry.get("field")),
                        start_year=entry.get("start_year"),
                        end_year=entry.get("end_year"),
                    ))

        # Calculate years of experience
        years_exp = self._calculate_years_experience(experience)

        # Build headline
        headline = clean_string(merged.get("headline"))
        if not headline:
            # Try to construct from title and company
            title = clean_string(merged.get("title"))
            company = clean_string(merged.get("current_company"))
            if title and company:
                headline = f"{title} at {company}"
            elif title:
                headline = title

        return CanonicalProfile(
            candidate_id=candidate_id,
            full_name=name,
            emails=merged.get("emails", []),
            phones=merged.get("phones", []),
            location=location,
            links=links,
            headline=headline,
            years_experience=years_exp,
            skills=skills,
            experience=experience,
            education=education,
            provenance=[],  # Will be set by provenance tracker
            overall_confidence=0.0,  # Will be set by confidence engine
        )

    def _calculate_years_experience(self, experience: list[Experience]) -> float | None:
        """Calculate total years of experience from experience entries.

        Uses start and end dates to compute duration.
        """
        if not experience:
            return None

        total_months = 0
        for exp in experience:
            start = exp.start
            end = exp.end

            if not start:
                continue

            try:
                start_year, start_month = map(int, start.split("-"))

                if end is None:
                    # Current job -- use current date
                    from datetime import date
                    today = date.today()
                    end_year, end_month = today.year, today.month
                else:
                    end_year, end_month = map(int, end.split("-"))

                months = (end_year - start_year) * 12 + (end_month - start_month)
                total_months += max(0, months)
            except (ValueError, AttributeError):
                continue

        if total_months > 0:
            return round(total_months / 12, 1)
        return None

    def _write_audit(
        self,
        output: dict[str, Any],
        field_confidences: dict[str, float],
    ) -> None:
        """Write the audit report to disk."""
        report = self.audit.generate_report(output, field_confidences)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        audit_path = self.output_dir / "audit_report.json"
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Written: %s", audit_path)
