"""
LinkedIn Profile Parser — unstructured source (TXT).

Parses LinkedIn profile data exported as a text file.
Uses section-based parsing to extract:
- Name, headline, location
- Experience entries
- Education entries
- Skills

Source reliability: 0.85 (self-reported but curated, generally accurate)
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


class LinkedInParser(BaseParser):
    """Parser for LinkedIn profile text exports."""

    source_type = "unstructured"
    source_name = "linkedin"

    # Section headers in LinkedIn text exports
    SECTION_HEADERS: dict[str, list[str]] = {
        "about": ["about", "summary", "about me"],
        "experience": ["experience", "work experience"],
        "education": ["education"],
        "skills": ["skills", "skills & endorsements", "top skills"],
        "certifications": ["certifications", "licenses & certifications"],
        "contact": ["contact", "contact info", "contact information"],
    }

    def can_parse(self, file_path: Path) -> bool:
        """Check if the file is a LinkedIn text export."""
        return (
            file_path.suffix.lower() == ".txt"
            and "linkedin" in file_path.name.lower()
        )

    def parse(self, file_path: Path) -> ExtractedRecord:
        """Parse a LinkedIn text export into an ExtractedRecord.

        Args:
            file_path: Path to the LinkedIn text file.

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
            logger.warning("LinkedIn file %s is empty", file_path.name)
            return self._empty_record(file_path)

        raw_fields: dict[str, Any] = {}

        # Extract contact info
        emails = extract_emails(text)
        if emails:
            raw_fields["emails"] = emails

        phones = extract_phone_numbers(text)
        if phones:
            raw_fields["phones"] = phones

        # Split into sections
        sections = self._split_sections(text)

        # Name — usually first line before any section
        name = self._extract_name(text)
        if name:
            raw_fields["full_name"] = name

        # Headline — usually second line or in About section
        headline = self._extract_headline(text, sections)
        if headline:
            raw_fields["headline"] = headline

        # Location — often third line
        location = self._extract_location(text)
        if location:
            raw_fields["location"] = location

        # About → headline fallback or summary
        if "about" in sections:
            about_text = sections["about"].strip()
            if about_text and "headline" not in raw_fields:
                first_line = about_text.split("\n")[0].strip()
                if first_line:
                    raw_fields["headline"] = first_line[:200]

        # Skills
        if "skills" in sections:
            skills = self._extract_skills(sections["skills"])
            if skills:
                raw_fields["skills"] = skills

        # Experience
        if "experience" in sections:
            experience = self._extract_experience(sections["experience"])
            if experience:
                raw_fields["experience"] = experience

        # Education
        if "education" in sections:
            education = self._extract_education(sections["education"])
            if education:
                raw_fields["education"] = education

        # Links
        urls = re.findall(r"https?://\S+", text)
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
            "LinkedIn profile parsed: %d fields extracted from %s",
            len(raw_fields),
            file_path.name,
        )

        return ExtractedRecord(
            source=self.source_name,
            source_file=file_path.name,
            raw_fields=raw_fields,
            extraction_method="text_section_parse",
            extraction_confidence=0.75,
        )

    def _empty_record(self, file_path: Path) -> ExtractedRecord:
        """Return an empty record for error cases."""
        return ExtractedRecord(
            source=self.source_name,
            source_file=file_path.name,
            raw_fields={},
            extraction_method="text_section_parse",
            extraction_confidence=0.0,
        )

    def _split_sections(self, text: str) -> dict[str, str]:
        """Split LinkedIn text into sections by headers."""
        sections: dict[str, str] = {}
        current_section: str | None = None
        current_lines: list[str] = []

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                if current_section:
                    current_lines.append("")
                continue

            # Check if this is a section header
            detected = self._detect_section(stripped)
            if detected:
                if current_section:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = detected
                current_lines = []
            elif current_section:
                current_lines.append(stripped)

        if current_section:
            sections[current_section] = "\n".join(current_lines).strip()

        return sections

    def _detect_section(self, line: str) -> str | None:
        """Detect if a line is a section header."""
        cleaned = line.strip().lower().rstrip(":")
        for section, headers in self.SECTION_HEADERS.items():
            if cleaned in headers:
                return section
        return None

    def _extract_name(self, text: str) -> str | None:
        """Extract name from first lines of LinkedIn profile."""
        lines = text.strip().split("\n")
        for line in lines[:3]:
            line = line.strip()
            if not line:
                continue
            # Skip section headers
            if self._detect_section(line):
                continue
            # Name: 2-4 words, mostly alpha
            words = line.split()
            if 2 <= len(words) <= 4 and all(
                re.match(r"^[A-Za-z.\-']+$", w) for w in words
            ):
                return line
        return None

    def _extract_headline(self, text: str, sections: dict[str, str]) -> str | None:
        """Extract professional headline."""
        lines = text.strip().split("\n")
        # Headline is usually the second non-empty line
        non_empty = [l.strip() for l in lines[:6] if l.strip()]
        if len(non_empty) >= 2:
            candidate = non_empty[1]
            if not self._detect_section(candidate) and len(candidate) > 5:
                return candidate[:200]
        return None

    def _extract_location(self, text: str) -> str | None:
        """Extract location from early lines."""
        lines = text.strip().split("\n")
        non_empty = [l.strip() for l in lines[:6] if l.strip()]
        for line in non_empty[2:4]:
            # Location patterns: "City, State" or "City, Country"
            if re.match(r"^[A-Za-z\s]+,\s*[A-Za-z\s]+$", line):
                return line
        return None

    def _extract_skills(self, text: str) -> list[str]:
        """Extract skills from the skills section."""
        skills: list[str] = []
        for line in text.split("\n"):
            skill = line.strip().strip("•●▪·-").strip()
            if skill and len(skill) < 50 and not skill.startswith("http"):
                # Handle comma-separated skills on one line
                if "," in skill:
                    skills.extend(s.strip() for s in skill.split(",") if s.strip())
                else:
                    skills.append(skill)
        return skills

    def _extract_experience(self, text: str) -> list[dict[str, str]]:
        """Extract experience entries from the experience section."""
        entries: list[dict[str, str]] = []
        lines = text.split("\n")
        current_entry: dict[str, str] = {}
        summary_lines: list[str] = []

        date_pattern = re.compile(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})"
            r"\s*[-–—to]+\s*"
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|Present|Current)",
            re.IGNORECASE,
        )

        for line in lines:
            line = line.strip()
            if not line:
                continue

            date_match = date_pattern.search(line)
            if date_match:
                if current_entry:
                    if summary_lines:
                        current_entry["summary"] = " ".join(summary_lines)
                    entries.append(current_entry)
                current_entry = {
                    "start": date_match.group(1),
                    "end": date_match.group(2),
                }
                summary_lines = []
                remaining = date_pattern.sub("", line).strip(" |-–—")
                if remaining:
                    current_entry["company"] = remaining
            elif current_entry:
                if not current_entry.get("company") and len(line.split()) <= 8:
                    current_entry["company"] = line
                elif not current_entry.get("title") and len(line.split()) <= 8:
                    current_entry["title"] = line
                else:
                    summary_lines.append(line)

        if current_entry:
            if summary_lines:
                current_entry["summary"] = " ".join(summary_lines)
            entries.append(current_entry)

        return entries

    def _extract_education(self, text: str) -> list[dict[str, Any]]:
        """Extract education entries from the education section."""
        entries: list[dict[str, Any]] = []
        lines = text.split("\n")

        degree_re = re.compile(
            r"(?:B\.?(?:Tech|S|Sc|E|A|Com)|Bachelor|M\.?(?:Tech|S|Sc|E|A|Com|BA)|Master|MBA|Ph\.?D|Doctorate)",
            re.IGNORECASE,
        )
        year_re = re.compile(r"\b(20\d{2}|19\d{2})\b")

        current_entry: dict[str, Any] = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            degree_match = degree_re.search(line)
            year_match = year_re.search(line)

            if degree_match or year_match:
                if current_entry and current_entry.get("institution"):
                    entries.append(current_entry)
                    current_entry = {}

                if degree_match:
                    current_entry["degree"] = degree_match.group(0)
                if year_match:
                    years = year_re.findall(line)
                    current_entry["end_year"] = int(years[-1])

                remaining = line
                if degree_match:
                    remaining = remaining[:degree_match.start()] + remaining[degree_match.end():]
                remaining = re.sub(r"\d{4}", "", remaining).strip(" ,|-–—")
                parts = [p.strip() for p in re.split(r"[,|–—]", remaining) if p.strip()]
                if parts:
                    current_entry["institution"] = parts[0]
                    if len(parts) > 1:
                        current_entry["field"] = parts[1]

            elif not current_entry.get("institution") and len(line.split()) >= 2:
                current_entry["institution"] = line

        if current_entry and current_entry.get("institution"):
            entries.append(current_entry)

        return entries
