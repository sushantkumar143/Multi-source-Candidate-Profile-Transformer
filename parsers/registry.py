"""
Parser registry — plug-and-play parser discovery.

The registry holds all registered parsers and provides:
- Automatic file detection across all registered parsers
- Parsing of all discovered files
- Easy registration of new parsers

To add a new parser (e.g., IndeedParser):
    1. Create indeed_parser.py implementing BaseParser
    2. In registry setup: ParserRegistry.register(IndeedParser())
    That's it — no other code changes needed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from parsers.base import BaseParser
from schemas.extracted import ExtractedRecord

logger = logging.getLogger(__name__)


class ParserRegistry:
    """Registry of available parsers.

    Provides file detection and parsing across all registered parsers.
    """

    def __init__(self) -> None:
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        """Register a parser instance.

        Args:
            parser: A BaseParser implementation.
        """
        self._parsers.append(parser)
        logger.debug("Registered parser: %s", parser)

    @property
    def parsers(self) -> list[BaseParser]:
        """Get all registered parsers."""
        return list(self._parsers)

    def detect_and_parse(self, input_dir: Path) -> list[ExtractedRecord]:
        """Scan input directory and parse all recognized files.

        Each file in the directory is tested against all registered parsers.
        If a parser can handle the file, it parses it. A single file can
        be parsed by at most one parser (first match wins).

        Args:
            input_dir: Path to the input directory.

        Returns:
            List of ExtractedRecords from all successfully parsed files.
        """
        if not input_dir.is_dir():
            logger.error("Input path is not a directory: %s", input_dir)
            return []

        records: list[ExtractedRecord] = []
        files = sorted(input_dir.iterdir())
        parsed_files: set[str] = set()

        for file_path in files:
            if not file_path.is_file():
                continue

            # Skip config files — they're handled separately
            if file_path.name.lower() in ("config.json",):
                continue

            for parser in self._parsers:
                if parser.can_parse(file_path):
                    logger.info(
                        "Parsing %s with %s",
                        file_path.name,
                        parser.__class__.__name__,
                    )
                    try:
                        record = parser.parse(file_path)
                        if record.raw_fields:
                            records.append(record)
                            parsed_files.add(file_path.name)
                            logger.info(
                                "Successfully extracted %d fields from %s",
                                len(record.raw_fields),
                                file_path.name,
                            )
                        else:
                            logger.warning(
                                "Parser %s returned no data for %s",
                                parser.__class__.__name__,
                                file_path.name,
                            )
                    except Exception as e:
                        logger.error(
                            "Parser %s failed on %s: %s",
                            parser.__class__.__name__,
                            file_path.name,
                            e,
                        )
                    break  # First matching parser wins

        unparsed = [
            f.name
            for f in files
            if f.is_file()
            and f.name not in parsed_files
            and f.name.lower() != "config.json"
        ]
        if unparsed:
            logger.warning("Unrecognized files (no parser matched): %s", unparsed)

        logger.info(
            "Source detection complete: %d files parsed, %d records extracted",
            len(parsed_files),
            len(records),
        )
        return records


def create_default_registry() -> ParserRegistry:
    """Create a registry with all default parsers registered.

    Returns:
        ParserRegistry with CSV, Resume, GitHub, LinkedIn, and Recruiter Notes parsers.
    """
    from parsers.csv_parser import CsvParser
    from parsers.resume_parser import ResumeParser
    from parsers.github_parser import GithubWebParser
    from parsers.linkedin_parser import LinkedInParser
    from parsers.recruiter_notes_parser import RecruiterNotesParser

    registry = ParserRegistry()
    registry.register(CsvParser())
    registry.register(ResumeParser())
    registry.register(GithubWebParser())
    registry.register(LinkedInParser())
    registry.register(RecruiterNotesParser())
    return registry
