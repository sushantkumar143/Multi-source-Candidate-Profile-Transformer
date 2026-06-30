"""
Recruiter Notes Parser — unstructured source (TXT).

Parses free-text recruiter notes using regex pattern matching.
Extracts mentions of:
- Candidate name
- Companies (current/previous)
- Skills and technologies
- Phone numbers and emails
- Education mentions

This is the lowest-reliability source (0.50) as recruiter notes
are informal, potentially subjective, and may be outdated.

Source reliability: 0.50
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from parsers.base import BaseParser
from schemas.extracted import ExtractedRecord
from utils.helpers import extract_emails, extract_phone_numbers

logger = logging.getLogger(__name__)


class RecruiterNotesParser(BaseParser):
    """Parser for free-text recruiter notes."""

    source_type = "unstructured"
    source_name = "recruiter_notes"

    # Patterns to extract structured info from free text
    COMPANY_PATTERNS: list[str] = [
        r"(?:currently|presently)\s+(?:at|with|working\s+at|employed\s+at)\s+([A-Z][A-Za-z\s&.]+?)(?:\.|,|\s*$)",
        r"(?:previously|formerly|was)\s+(?:at|with)\s+([A-Z][A-Za-z\s&.]+?)(?:\.|,|\s*$)",
        r"(?:works?\s+at|working\s+at|employed\s+at)\s+([A-Z][A-Za-z\s&.]+?)(?:\.|,|\s*$)",
    ]

    SKILL_INTRO_PATTERNS: list[str] = [
        r"(?:knows?|skilled?\s+in|proficient\s+in|experienced?\s+(?:in|with)|strong\s+(?:in)?|expertise\s+in|familiar\s+with)\s*:?\s*(.+)",
        r"(?:tech\s+stack|technologies|skills?)\s*:?\s*(.+)",
    ]

    EDUCATION_PATTERNS: list[str] = [
        r"((?:IIT|NIT|BITS|MIT|Stanford|Harvard|Berkeley|IIIT|VIT|SRM|DTU)\s*[A-Za-z]*)",
        r"((?:B\.?Tech|M\.?Tech|B\.?S|M\.?S|MBA|Ph\.?D)[^,.\n]*)",
    ]

    def can_parse(self, file_path: Path) -> bool:
        """Check if the file is a recruiter notes text file."""
        name_lower = file_path.name.lower()
        return file_path.suffix.lower() == ".txt" and (
            "recruiter" in name_lower
            or "notes" in name_lower
        ) and "linkedin" not in name_lower

    def parse(self, file_path: Path) -> ExtractedRecord:
        """Parse recruiter notes into an ExtractedRecord.

        Args:
            file_path: Path to the recruiter notes file.

        Returns:
            ExtractedRecord with extracted fields.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            logger.error("Failed to read %s: %s", file_path.name, e)
            return self._empty_record(file_path)

        if not text.strip():
            logger.warning("Recruiter notes file %s is empty", file_path.name)
            return self._empty_record(file_path)

        raw_fields: dict[str, Any] = {}

        # Extract contact info
        emails = extract_emails(text)
        if emails:
            raw_fields["emails"] = emails

        phones = extract_phone_numbers(text)
        if phones:
            raw_fields["phones"] = phones

        # Extract name (look for patterns like "Spoke with <Name>" or "Candidate: <Name>")
        name = self._extract_name(text)
        if name:
            raw_fields["full_name"] = name

        # Extract companies
        companies = self._extract_companies(text)
        if companies:
            raw_fields["current_company"] = companies[0]  # Most recent
            if len(companies) > 1:
                raw_fields["previous_companies"] = companies[1:]

        # Extract skills
        skills = self._extract_skills(text)
        if skills:
            raw_fields["skills"] = skills

        # Extract education
        education = self._extract_education(text)
        if education:
            raw_fields["education"] = education

        # Extract any URLs
        urls = re.findall(r"https?://\S+", text)
        if urls:
            links: dict[str, Any] = {}
            for url in urls:
                url_clean = url.rstrip(".,;)")
                if "linkedin.com" in url_clean.lower():
                    links["linkedin"] = url_clean
                elif "github.com" in url_clean.lower():
                    links["github"] = url_clean
                else:
                    links.setdefault("other", []).append(url_clean)
            if links:
                raw_fields["links"] = links

        logger.info(
            "Recruiter notes parsed: %d fields extracted from %s",
            len(raw_fields),
            file_path.name,
        )

        return ExtractedRecord(
            source=self.source_name,
            source_file=file_path.name,
            raw_fields=raw_fields,
            extraction_method="regex_match",
            extraction_confidence=0.50,
        )

    def _empty_record(self, file_path: Path) -> ExtractedRecord:
        """Return an empty record for error cases."""
        return ExtractedRecord(
            source=self.source_name,
            source_file=file_path.name,
            raw_fields={},
            extraction_method="regex_match",
            extraction_confidence=0.0,
        )

    def _extract_name(self, text: str) -> str | None:
        """Extract candidate name from recruiter notes."""
        patterns = [
            r"(?:spoke|talked|met|interviewed|call)\s+(?:with|to)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
            r"(?:candidate|applicant)\s*:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)",
            r"(?:name|regarding)\s*:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_companies(self, text: str) -> list[str]:
        """Extract company names from recruiter notes."""
        companies: list[str] = []
        for pattern in self.COMPANY_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                company = match.strip().rstrip(".,")
                if company and len(company) > 1 and company not in companies:
                    companies.append(company)
        return companies

    def _extract_skills(self, text: str) -> list[str]:
        """Extract skills and technologies from recruiter notes."""
        skills: list[str] = []
        seen: set[str] = set()

        # Try skill introduction patterns
        for pattern in self.SKILL_INTRO_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # Split by common delimiters
                for delimiter in [",", " and ", " & ", "|"]:
                    if delimiter in match:
                        parts = match.split(delimiter)
                        for part in parts:
                            skill = part.strip().rstrip(".")
                            if skill and len(skill) < 40 and skill.lower() not in seen:
                                seen.add(skill.lower())
                                skills.append(skill)
                        break
                else:
                    skill = match.strip().rstrip(".")
                    if skill and len(skill) < 40 and skill.lower() not in seen:
                        seen.add(skill.lower())
                        skills.append(skill)

        return skills

    def _extract_education(self, text: str) -> list[dict[str, Any]]:
        """Extract education mentions from recruiter notes."""
        entries: list[dict[str, Any]] = []
        seen_institutions: set[str] = set()

        for pattern in self.EDUCATION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if match and match.lower() not in seen_institutions:
                    seen_institutions.add(match.lower())
                    entry: dict[str, Any] = {}

                    # Check if it's a degree or institution
                    if re.match(r"(?:B\.?Tech|M\.?Tech|B\.?S|M\.?S|MBA|Ph\.?D)", match, re.IGNORECASE):
                        # It's a degree
                        parts = re.split(r"\s+(?:in|from)\s+", match, flags=re.IGNORECASE)
                        entry["degree"] = parts[0].strip()
                        if len(parts) > 1:
                            entry["field"] = parts[1].strip()
                    else:
                        entry["institution"] = match

                    # Look for year nearby
                    year_match = re.search(
                        rf"(?:{re.escape(match)}[^.]*?(\b(?:20|19)\d{{2}}\b))",
                        text,
                    )
                    if year_match:
                        entry["end_year"] = int(year_match.group(1))

                    entries.append(entry)

        return entries
