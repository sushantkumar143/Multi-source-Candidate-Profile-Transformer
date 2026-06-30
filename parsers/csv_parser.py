"""
CSV Parser — structured source.

Parses candidate.csv files with structured rows containing
fields like name, email, phone, current_company, title, location.
Handles missing columns gracefully.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from parsers.base import BaseParser
from schemas.extracted import ExtractedRecord

logger = logging.getLogger(__name__)


class CsvParser(BaseParser):
    """Parser for CSV candidate exports."""

    source_type = "structured"
    source_name = "csv"

    # Map CSV column names to canonical field names
    COLUMN_MAP: dict[str, str] = {
        "name": "full_name",
        "full_name": "full_name",
        "candidate_name": "full_name",
        "email": "emails",
        "emails": "emails",
        "email_address": "emails",
        "phone": "phones",
        "phones": "phones",
        "phone_number": "phones",
        "current_company": "current_company",
        "company": "current_company",
        "employer": "current_company",
        "title": "title",
        "job_title": "title",
        "position": "title",
        "location": "location",
        "city": "city",
        "skills": "skills",
        "linkedin": "linkedin_url",
        "linkedin_url": "linkedin_url",
        "github": "github_url",
        "github_url": "github_url",
    }

    def can_parse(self, file_path: Path) -> bool:
        """Check if the file is a candidate CSV."""
        return (
            file_path.suffix.lower() == ".csv"
            and file_path.name.lower() in ("candidate.csv", "candidates.csv")
        )

    def parse(self, file_path: Path) -> ExtractedRecord:
        """Parse a CSV file into an ExtractedRecord.

        Reads the first row of the CSV (single candidate).
        Maps column names to canonical field names.

        Args:
            file_path: Path to the CSV file.

        Returns:
            ExtractedRecord with parsed data.
        """
        try:
            df = pd.read_csv(file_path, dtype=str)
        except Exception as e:
            logger.error("Failed to read CSV %s: %s", file_path.name, e)
            return ExtractedRecord(
                source=self.source_name,
                source_file=file_path.name,
                raw_fields={},
                extraction_method="structured_parse",
                extraction_confidence=0.0,
            )

        if df.empty:
            logger.warning("CSV file %s is empty", file_path.name)
            return ExtractedRecord(
                source=self.source_name,
                source_file=file_path.name,
                raw_fields={},
                extraction_method="structured_parse",
                extraction_confidence=0.0,
            )

        # Take the first row (single candidate)
        row = df.iloc[0]
        raw_fields: dict[str, Any] = {}

        for col in df.columns:
            col_lower = col.strip().lower()
            value = row[col]

            # Skip NaN/empty values
            if pd.isna(value) or str(value).strip() == "":
                continue

            canonical_name = self.COLUMN_MAP.get(col_lower, col_lower)
            value_str = str(value).strip()

            # Handle fields that should be lists
            if canonical_name in ("emails", "phones", "skills"):
                # Split comma-separated values
                if canonical_name in raw_fields:
                    existing = raw_fields[canonical_name]
                    if isinstance(existing, list):
                        existing.append(value_str)
                    else:
                        raw_fields[canonical_name] = [existing, value_str]
                else:
                    raw_fields[canonical_name] = [
                        v.strip() for v in value_str.split(",") if v.strip()
                    ]
            else:
                raw_fields[canonical_name] = value_str

        # Log mapped vs unmapped columns
        mapped = [c for c in df.columns if c.strip().lower() in self.COLUMN_MAP]
        unmapped = [c for c in df.columns if c.strip().lower() not in self.COLUMN_MAP]
        if unmapped:
            logger.info("CSV columns not in mapping (kept as-is): %s", unmapped)

        logger.info(
            "CSV parsed: %d fields extracted from %s",
            len(raw_fields),
            file_path.name,
        )

        return ExtractedRecord(
            source=self.source_name,
            source_file=file_path.name,
            raw_fields=raw_fields,
            extraction_method="structured_parse",
            extraction_confidence=0.9,  # High confidence for structured data
        )
