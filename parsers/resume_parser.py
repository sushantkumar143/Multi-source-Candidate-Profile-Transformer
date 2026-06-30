"""
Resume Parser — unstructured source (PDF).

Uses pdfplumber to extract text from PDF resumes,
then applies regex-based section detection to identify:
- Contact information (name, email, phone)
- Professional summary / headline
- Skills
- Work experience
- Education

Source reliability: 0.70 (unstructured, extraction may be imprecise)
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


class ResumeParser(BaseParser):
    """Parser for PDF resume files."""

    source_type = "unstructured"
    source_name = "resume"

    # Section header patterns (case-insensitive)
    SECTION_PATTERNS: dict[str, list[str]] = {
        "summary": [
            r"(?:professional\s+)?summary",
            r"(?:career\s+)?objective",
            r"about\s+me",
            r"profile",
        ],
        "experience": [
            r"(?:work\s+)?experience",
            r"employment(?:\s+history)?",
            r"professional\s+experience",
            r"career\s+history",
            r"work\s+history",
            r"internship.*",
            r"projects.*",
        ],
        "education": [
            r"education(?:al\s+background)?",
            r"academic(?:\s+background)?",
            r"qualifications",
        ],
        "skills": [
            r"(?:technical\s+)?skills",
            r"technologies",
            r"competencies",
            r"tools?\s+(?:and|&)\s+technologies",
            r"tech(?:nical)?\s+stack",
        ],
    }

    def can_parse(self, file_path: Path) -> bool:
        """Check if the file is a PDF resume."""
        return (
            file_path.suffix.lower() == ".pdf"
            and "resume" in file_path.name.lower()
        )

    def parse(self, file_path: Path) -> ExtractedRecord:
        """Parse a PDF resume into an ExtractedRecord.

        Extracts text using pdfplumber, then identifies sections
        and extracts structured information.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ExtractedRecord with extracted fields.
        """
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber not installed — cannot parse PDF resumes")
            return self._empty_record(file_path)

        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.error("Failed to extract text from PDF %s: %s", file_path.name, e)
            return self._empty_record(file_path)

        if not text.strip():
            logger.warning("PDF %s yielded no text", file_path.name)
            return self._empty_record(file_path)

        raw_fields: dict[str, Any] = {}

        # Extract contact info
        emails = extract_emails(text)
        if emails:
            raw_fields["emails"] = emails

        phones = extract_phone_numbers(text)
        if phones:
            raw_fields["phones"] = phones

        # Try to extract name (usually first non-empty line)
        name = self._extract_name(text)
        if name:
            raw_fields["full_name"] = name

        # Extract sections
        sections = self._split_sections(text)

        # Summary → headline
        if "summary" in sections:
            summary_text = sections["summary"].strip()
            if summary_text:
                # Take first sentence or first 200 chars as headline
                first_sentence = re.split(r"[.\n]", summary_text)[0].strip()
                if first_sentence:
                    raw_fields["headline"] = first_sentence[:200]

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

        # Extract links
        urls = re.findall(
            r"https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_+.~#?&/=]*)",
            text,
        )
        if urls:
            links: dict[str, Any] = {}
            for url in urls:
                url_lower = url.lower()
                if "linkedin.com" in url_lower:
                    links["linkedin"] = url
                elif "github.com" in url_lower:
                    links["github"] = url
                else:
                    links.setdefault("other", []).append(url)
            if links:
                raw_fields["links"] = links

        logger.info(
            "Resume parsed: %d fields extracted from %s",
            len(raw_fields),
            file_path.name,
        )

        return ExtractedRecord(
            source=self.source_name,
            source_file=file_path.name,
            raw_fields=raw_fields,
            extraction_method="pdf_text_extract",
            extraction_confidence=0.65,
        )

    def _empty_record(self, file_path: Path) -> ExtractedRecord:
        """Return an empty record for error cases."""
        return ExtractedRecord(
            source=self.source_name,
            source_file=file_path.name,
            raw_fields={},
            extraction_method="pdf_text_extract",
            extraction_confidence=0.0,
        )

    def _extract_name(self, text: str) -> str | None:
        """Extract candidate name from resume text.

        Assumes name is in the first few lines, before any section headers.
        Looks for a line that looks like a name (2-4 capitalized words).
        """
        lines = text.strip().split("\n")
        for line in lines[:5]:
            line = line.strip()
            if not line or len(line) < 3:
                continue
            # Skip lines that look like addresses or contact info
            if "@" in line or re.search(r"\d{5,}", line):
                continue
            # Check if it looks like a name (2-4 words, mostly alpha)
            words = line.split()
            if 2 <= len(words) <= 4 and all(
                re.match(r"^[A-Za-z.\-']+$", w) for w in words
            ):
                return line
        return None

    def _split_sections(self, text: str) -> dict[str, str]:
        """Split resume text into sections based on headers.

        Returns:
            Dict mapping section name to section content.
        """
        sections: dict[str, str] = {}
        current_section: str | None = None
        current_content: list[str] = []

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                if current_section:
                    current_content.append("")
                continue

            # Check if this line is a section header
            detected_section = self._detect_section(stripped)
            if detected_section:
                # Save previous section
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = detected_section
                current_content = []
            elif current_section:
                current_content.append(stripped)

        # Save last section
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _detect_section(self, line: str) -> str | None:
        """Detect if a line is a section header."""
        cleaned = re.sub(r"[:\-–—|]", "", line).strip()
        for section_name, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.match(rf"^{pattern}$", cleaned, re.IGNORECASE):
                    return section_name
        return None

    def _extract_skills(self, text: str) -> list[str]:
        """Extract skills from the skills section."""
        # Split by common delimiters
        skills: list[str] = []
        for delimiter in [",", "|", "•", "●", "▪", "·", "\n"]:
            if delimiter in text:
                parts = text.split(delimiter)
                for part in parts:
                    skill = part.strip().strip("-•●▪·").strip()
                    if skill and len(skill) < 50 and not skill.startswith("http"):
                        skills.append(skill)
                break
        else:
            # Fallback: split by newlines
            for line in text.split("\n"):
                skill = line.strip().strip("-•●▪·").strip()
                if skill and len(skill) < 50:
                    skills.append(skill)

        return skills

    def _extract_experience(self, text: str) -> list[dict[str, str]]:
        """Extract work experience entries.

        Looks for patterns like:
        - Company Name | Title
        - Title at Company
        - Date ranges (MMM YYYY - MMM YYYY)
        """
        entries: list[dict[str, str]] = []
        lines = text.split("\n")
        current_entry: dict[str, str] = {}
        summary_lines: list[str] = []

        # Date pattern: various formats
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

            # Check for date range
            date_match = date_pattern.search(line)
            if date_match:
                # Save previous entry
                if current_entry:
                    if summary_lines:
                        current_entry["summary"] = " ".join(summary_lines)
                    entries.append(current_entry)

                current_entry = {
                    "start": date_match.group(1),
                    "end": date_match.group(2),
                }
                summary_lines = []

                # Extract company/title from the same line or context
                remaining = date_pattern.sub("", line).strip(" |-–—")
                if remaining:
                    if "|" in remaining:
                        parts = remaining.split("|")
                        current_entry["company"] = parts[0].strip()
                        if len(parts) > 1:
                            current_entry["title"] = parts[1].strip()
                    elif " at " in remaining.lower():
                        parts = re.split(r"\s+at\s+", remaining, flags=re.IGNORECASE)
                        current_entry["title"] = parts[0].strip()
                        if len(parts) > 1:
                            current_entry["company"] = parts[1].strip()
                    else:
                        current_entry["company"] = remaining

            elif current_entry:
                # Check if this looks like a company/title line
                if not current_entry.get("company") and "|" in line:
                    parts = line.split("|")
                    current_entry["company"] = parts[0].strip()
                    if len(parts) > 1:
                        current_entry["title"] = parts[1].strip()
                elif not current_entry.get("title") and len(line.split()) <= 6:
                    # Short lines might be titles
                    if not current_entry.get("company"):
                        current_entry["company"] = line
                    elif not current_entry.get("title"):
                        current_entry["title"] = line
                else:
                    summary_lines.append(line)

        # Save last entry
        if current_entry:
            if summary_lines:
                current_entry["summary"] = " ".join(summary_lines)
            entries.append(current_entry)

        return entries

    def _extract_education(self, text: str) -> list[dict[str, Any]]:
        """Extract education entries.

        Looks for patterns like:
        - University Name, Degree in Field, Year
        - B.Tech / B.S. / M.S. / MBA etc.
        """
        entries: list[dict[str, Any]] = []
        lines = text.split("\n")

        degree_patterns = [
            r"(?:B\.?(?:Tech|S|Sc|E|A|Com)\b|Bachelor(?:'s)?(?:\s+of\s+[A-Za-z\s]+)?)",
            r"(?:M\.?(?:Tech|S|Sc|E|A|Com|BA)\b|Master(?:'s)?(?:\s+of\s+[A-Za-z\s]+)?)",
            r"(?:Ph\.?D\.?|Doctorate)",
        ]
        degree_re = re.compile("|".join(degree_patterns), re.IGNORECASE)
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
                    if (degree_match and current_entry.get("degree")) or (year_match and (current_entry.get("end_year") or current_entry.get("start_year"))):
                        entries.append(current_entry)
                        current_entry = {}

                if degree_match:
                    current_entry["degree"] = degree_match.group(0)

                if year_match:
                    years = year_re.findall(line)
                    if "since" in line.lower() or "present" in line.lower() or "current" in line.lower():
                        current_entry["start_year"] = int(years[0])
                        current_entry["end_year"] = None
                    elif len(years) >= 2:
                        current_entry["start_year"] = int(years[0])
                        current_entry["end_year"] = int(years[-1])
                    else:
                        current_entry["end_year"] = int(years[0])

                # Try to extract institution and field
                remaining = line
                if degree_match:
                    remaining = remaining[: degree_match.start()] + remaining[degree_match.end() :]
                remaining = re.sub(r"\d{4}", "", remaining)
                remaining = remaining.strip(" ,|-–—")

                # Split by common separators
                parts = re.split(r"[,|–—]", remaining)
                parts = [p.strip() for p in parts if p.strip()]
                if parts:
                    if not current_entry.get("institution"):
                        current_entry["institution"] = parts[0]
                    if len(parts) > 1 and not current_entry.get("field"):
                        current_entry["field"] = parts[1]

            elif not current_entry.get("institution") and len(line.split()) >= 2:
                current_entry["institution"] = line

        if current_entry and current_entry.get("institution"):
            entries.append(current_entry)

        return entries
