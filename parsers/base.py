"""
Abstract base class for all parsers.

Every parser in the pipeline inherits from BaseParser and implements:
- can_parse(): determine if the parser can handle a given file
- parse(): extract data from the file into an ExtractedRecord

This enables the plug-and-play architecture: new parsers
(e.g., IndeedParser, NaukriParser) can be added without
modifying existing code — they just implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from schemas.extracted import ExtractedRecord


class BaseParser(ABC):
    """Abstract base class for all source parsers.

    Subclasses must define:
        source_type: "structured" or "unstructured"
        source_name: unique identifier (e.g., "csv", "resume", "github")

    And implement:
        can_parse(): file detection logic
        parse(): data extraction logic
    """

    source_type: str  # "structured" or "unstructured"
    source_name: str  # unique parser identifier

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Determine if this parser can handle the given file.

        Args:
            file_path: Path to the input file.

        Returns:
            True if this parser should process the file.
        """
        ...

    @abstractmethod
    def parse(self, file_path: Path) -> ExtractedRecord:
        """Extract data from the file into an ExtractedRecord.

        Must never raise exceptions — returns an empty ExtractedRecord
        on failure with appropriate logging.

        Args:
            file_path: Path to the input file.

        Returns:
            ExtractedRecord with raw extracted fields.
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source={self.source_name}, type={self.source_type})"
