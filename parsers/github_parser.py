"""
GitHub Web Parser.

Reads a `links.json` file, extracts the GitHub URL, and fetches data dynamically:
1. Tries to get the profile README from `https://api.github.com/repos/{user}/{user}/readme`
2. If not found, falls back to scraping the profile HTML using BeautifulSoup.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from parsers.base import BaseParser
from schemas.extracted import ExtractedRecord

logger = logging.getLogger(__name__)


class GithubWebParser(BaseParser):
    """Parser for GitHub profiles dynamically fetched from the web."""

    source_type = "web"
    source_name = "github"

    def can_parse(self, file_path: Path) -> bool:
        """Check if the file is links.json containing a github URL."""
        if file_path.name.lower() == "links.json":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return "github" in data or "github_url" in data
            except Exception:
                return False
        return False

    def parse(self, file_path: Path) -> ExtractedRecord:
        """Parse a GitHub profile dynamically based on links.json.

        Args:
            file_path: Path to links.json.

        Returns:
            ExtractedRecord with extracted fields.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data: dict[str, str] = json.load(f)
        except Exception as e:
            logger.error("Failed to read %s: %s", file_path.name, e)
            return self._empty_record(file_path)

        github_url = data.get("github_url") or data.get("github")
        if not github_url:
            return self._empty_record(file_path)

        # Extract username
        # Expected format: https://github.com/username
        match = re.search(r"github\.com/([^/]+)", github_url)
        if not match:
            logger.error("Could not extract username from GitHub URL: %s", github_url)
            return self._empty_record(file_path)
            
        username = match.group(1).strip()
        logger.info("Fetching GitHub data for user: %s", username)

        raw_fields: dict[str, Any] = {
            "links": {"github": github_url}
        }

        # Try API first (Profile README)
        readme_content = self._fetch_readme(username)
        if readme_content:
            logger.info("Successfully fetched GitHub README for %s", username)
            skills = self._extract_skills_from_text(readme_content)
            if skills:
                raw_fields["skills"] = skills
            # Attempt to find email in README
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", readme_content)
            if email_match:
                raw_fields["emails"] = [email_match.group(0).lower()]
            method = "github_api_readme"
            confidence = 0.85
        else:
            # Fallback to BeautifulSoup scraping
            logger.info("README not found, falling back to HTML scraping for %s", username)
            html_fields = self._scrape_html(github_url)
            raw_fields.update(html_fields)
            method = "github_html_scrape"
            confidence = 0.70

        if len(raw_fields) <= 1:
            logger.warning("No meaningful data extracted from GitHub for %s", username)

        return ExtractedRecord(
            source=self.source_name,
            source_file=file_path.name,
            raw_fields=raw_fields,
            extraction_method=method,
            extraction_confidence=confidence,
        )

    def _fetch_readme(self, username: str) -> str | None:
        """Fetch the profile README using the GitHub REST API."""
        url = f"https://api.github.com/repos/{username}/{username}/readme"
        try:
            # Set a timeout so we don't hang the pipeline
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                content_b64 = data.get("content", "")
                if content_b64:
                    return base64.b64decode(content_b64).decode("utf-8", errors="ignore")
            return None
        except Exception as e:
            logger.warning("Failed to fetch GitHub README: %s", e)
            return None

    def _scrape_html(self, url: str) -> dict[str, Any]:
        """Scrape the GitHub profile HTML using BeautifulSoup."""
        fields: dict[str, Any] = {}
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logger.warning("Failed to fetch GitHub HTML: status %d", response.status_code)
                return fields

            soup = BeautifulSoup(response.text, "html.parser")

            # Extract Name
            name_tag = soup.find("span", class_="p-name")
            if name_tag:
                fields["full_name"] = name_tag.get_text(strip=True)

            # Extract Bio
            bio_tag = soup.find("div", class_="p-note")
            if bio_tag:
                fields["headline"] = bio_tag.get_text(strip=True)

            # Extract Location
            loc_tag = soup.find("span", class_="p-label")
            if loc_tag:
                fields["location"] = loc_tag.get_text(strip=True)

            # Extract languages from pinned repos as skills
            skills = []
            lang_tags = soup.find_all("span", itemprop="programmingLanguage")
            for tag in lang_tags:
                lang = tag.get_text(strip=True)
                if lang and lang not in skills:
                    skills.append(lang)
            
            if skills:
                fields["skills"] = skills

        except Exception as e:
            logger.warning("Error scraping GitHub HTML: %s", e)

        return fields

    def _extract_skills_from_text(self, text: str) -> list[str]:
        """Basic regex-based skill extraction from text/markdown."""
        # Common tech skills to look for
        common_skills = [
            "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang",
            "rust", "ruby", "php", "swift", "kotlin", "scala", "sql", "nosql",
            "react", "angular", "vue", "node.js", "django", "flask", "fastapi",
            "spring", "docker", "kubernetes", "k8s", "aws", "azure", "gcp",
            "terraform", "ansible", "jenkins", "git", "linux", "machine learning",
            "ml", "ai", "data engineering", "spark", "hadoop", "kafka"
        ]
        
        found_skills = []
        text_lower = text.lower()
        
        # Word boundary match
        for skill in common_skills:
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, text_lower):
                # Title case for standard representation
                found_skills.append(skill.title() if len(skill) > 2 else skill.upper())
                
        # Deduplicate case-insensitively
        unique_skills = []
        seen = set()
        for s in found_skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                unique_skills.append(s)
                
        return unique_skills

    def _empty_record(self, file_path: Path) -> ExtractedRecord:
        """Return an empty record for error cases."""
        return ExtractedRecord(
            source=self.source_name,
            source_file=file_path.name,
            raw_fields={},
            extraction_method="web_parse",
            extraction_confidence=0.0,
        )
