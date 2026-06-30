"""
Field Extractor.

Takes raw ExtractedRecords from parsers and maps their raw_fields
to a consistent intermediate representation that the normalizer
and merger can work with.

This layer exists to decouple parsers from downstream processing.
Parsers can use any key names they like; the extractor maps them
to canonical field names.
"""

from __future__ import annotations

import logging
from typing import Any

from schemas.extracted import ExtractedRecord

logger = logging.getLogger(__name__)

# Mapping of common raw field names to canonical names
FIELD_ALIASES: dict[str, str] = {
    "name": "full_name",
    "full_name": "full_name",
    "candidate_name": "full_name",
    "applicant_name": "full_name",
    "email": "emails",
    "emails": "emails",
    "email_address": "emails",
    "contact_email": "emails",
    "phone": "phones",
    "phones": "phones",
    "phone_number": "phones",
    "contact_phone": "phones",
    "current_company": "current_company",
    "company": "current_company",
    "employer": "current_company",
    "current_employer": "current_company",
    "title": "title",
    "job_title": "title",
    "position": "title",
    "headline": "headline",
    "bio": "headline",
    "location": "location",
    "skills": "skills",
    "skills_list": "skills",
    "experience": "experience",
    "education": "education",
    "links": "links",
    "linkedin_url": "linkedin_url",
    "github_url": "github_url",
}


def extract_fields(record: ExtractedRecord) -> dict[str, Any]:
    """Extract and normalize field names from a raw record.

    Maps raw field names to canonical names using FIELD_ALIASES.
    Ensures list fields are always lists, scalar fields are strings.

    Args:
        record: An ExtractedRecord from any parser.

    Returns:
        Dictionary with canonical field names and cleaned values.
    """
    canonical: dict[str, Any] = {}

    for raw_key, value in record.raw_fields.items():
        # Skip internal/metadata fields (prefixed with _)
        if raw_key.startswith("_"):
            continue

        # Map to canonical name
        canonical_key = FIELD_ALIASES.get(raw_key.lower().strip(), raw_key.lower().strip())

        # Ensure list fields are lists
        if canonical_key in ("emails", "phones", "skills"):
            if isinstance(value, str):
                # Split comma-separated values
                value = [v.strip() for v in value.split(",") if v.strip()]
            elif not isinstance(value, list):
                value = [str(value)]

        # Handle nested structures (experience, education, links)
        if canonical_key in ("experience", "education"):
            if isinstance(value, dict):
                value = [value]
            elif not isinstance(value, list):
                continue  # Skip invalid types

        # Handle link fields
        if canonical_key == "linkedin_url":
            links = canonical.get("links", {})
            if not isinstance(links, dict):
                links = {}
            links["linkedin"] = str(value)
            canonical["links"] = links
            continue

        if canonical_key == "github_url":
            links = canonical.get("links", {})
            if not isinstance(links, dict):
                links = {}
            links["github"] = str(value)
            canonical["links"] = links
            continue

        # Store the value
        if canonical_key in canonical:
            # Merge list fields
            existing = canonical[canonical_key]
            if isinstance(existing, list) and isinstance(value, list):
                canonical[canonical_key] = existing + value
            elif isinstance(existing, dict) and isinstance(value, dict):
                existing.update(value)
            # For scalar conflicts, keep the first value
        else:
            canonical[canonical_key] = value

    logger.debug(
        "Extracted %d canonical fields from %s (%s)",
        len(canonical),
        record.source_file,
        record.source,
    )
    return canonical
