"""Normalizer modules for the pipeline."""

from normalizers.phone_normalizer import normalize_phones
from normalizers.date_normalizer import normalize_date
from normalizers.skill_normalizer import normalize_skills
from normalizers.location_normalizer import normalize_location
from normalizers.deduplicator import deduplicate

__all__ = [
    "normalize_phones",
    "normalize_date",
    "normalize_skills",
    "normalize_location",
    "deduplicate",
]
