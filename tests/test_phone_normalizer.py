"""
Tests for phone normalization.

Covers:
- Indian phone numbers (with/without country code)
- US phone numbers
- International formats
- Invalid numbers
- Edge cases
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from normalizers.phone_normalizer import normalize_phone, normalize_phones


class TestNormalizePhone:
    """Tests for single phone normalization."""

    def test_indian_number_without_country_code(self):
        """9876543210 → +919876543210"""
        result, success = normalize_phone("9876543210")
        assert success
        assert result == "+919876543210"

    def test_indian_number_with_country_code(self):
        """+919876543210 stays as +919876543210"""
        result, success = normalize_phone("+919876543210")
        assert success
        assert result == "+919876543210"

    def test_indian_number_with_spaces(self):
        """+91 98765 43210 → +919876543210"""
        result, success = normalize_phone("+91 98765 43210")
        assert success
        assert result == "+919876543210"

    def test_indian_number_with_dashes(self):
        """+91-98765-43210 → +919876543210"""
        result, success = normalize_phone("+91-98765-43210")
        assert success
        assert result == "+919876543210"

    def test_us_number(self):
        """+1-202-555-0123 → +12025550123"""
        result, success = normalize_phone("+1-202-555-0123", default_region="US")
        assert success
        assert result == "+12025550123"

    def test_us_number_without_country_code(self):
        """2025550123 with US region → +12025550123"""
        result, success = normalize_phone("2025550123", default_region="US")
        assert success
        assert result == "+12025550123"

    def test_empty_string(self):
        """Empty string returns empty and failure."""
        result, success = normalize_phone("")
        assert not success
        assert result == ""

    def test_invalid_number(self):
        """Clearly invalid number returns cleaned string and failure."""
        result, success = normalize_phone("123")
        assert not success


class TestNormalizePhones:
    """Tests for batch phone normalization."""

    def test_multiple_phones(self):
        """Normalize a list of phones."""
        phones = ["9876543210", "+919876543210"]
        normalized, transformations = normalize_phones(phones)
        assert len(normalized) == 2
        assert all(p.startswith("+91") for p in normalized)

    def test_empty_list(self):
        """Empty list returns empty."""
        normalized, transformations = normalize_phones([])
        assert normalized == []
        assert transformations == []

    def test_transformation_records(self):
        """Verify transformation records are generated."""
        phones = ["9876543210"]
        normalized, transformations = normalize_phones(phones)
        assert len(transformations) == 1
        assert transformations[0]["before"] == "9876543210"
        assert transformations[0]["after"] == "+919876543210"
