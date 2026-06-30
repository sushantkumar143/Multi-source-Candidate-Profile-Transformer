"""
Skill Normalizer.

Normalizes skill names to canonical representations:
- "python" → "Python"
- "PYTHON" → "Python"
- "python3" → "Python"
- "ml" → "Machine Learning"
- "k8s" → "Kubernetes"

Uses the canonical mapping from Settings.SKILL_CANONICAL_MAP.
Unknown skills are title-cased.
"""

from __future__ import annotations

import logging

from config.settings import Settings

logger = logging.getLogger(__name__)


def normalize_skill(raw_skill: str) -> tuple[str, bool]:
    """Normalize a single skill name to its canonical form.

    Args:
        raw_skill: Raw skill name.

    Returns:
        Tuple of (canonical_name, was_mapped).
        If the skill is in the canonical map, returns the mapped name.
        Otherwise, returns a title-cased version.
    """
    raw_skill = raw_skill.strip()
    if not raw_skill:
        return "", False

    lookup = raw_skill.lower().strip()

    # Check canonical mapping
    if lookup in Settings.SKILL_CANONICAL_MAP:
        canonical = Settings.SKILL_CANONICAL_MAP[lookup]
        if canonical != raw_skill:
            logger.debug("Skill normalized: %s → %s", raw_skill, canonical)
        return canonical, True

    # For unknown skills, apply smart title-casing
    # (preserves acronyms like "AWS", "SQL")
    if raw_skill.isupper() and len(raw_skill) <= 5:
        # Likely an acronym — keep as-is
        return raw_skill, False
    elif raw_skill.isupper():
        # All caps but long — title case it
        return raw_skill.title(), False
    elif raw_skill.islower():
        return raw_skill.title(), False
    else:
        # Mixed case — keep as-is (user probably intended it)
        return raw_skill, False


def normalize_skills(
    skills: list[str],
) -> tuple[list[str], list[dict[str, str]]]:
    """Normalize a list of skill names.

    Args:
        skills: List of raw skill names.

    Returns:
        Tuple of:
        - List of canonical skill names (deduplicated)
        - List of transformation records for audit
    """
    normalized: list[str] = []
    transformations: list[dict[str, str]] = []
    seen: set[str] = set()

    for skill in skills:
        canonical, was_mapped = normalize_skill(skill)
        if not canonical:
            continue

        # Deduplicate (case-insensitive)
        if canonical.lower() in seen:
            continue
        seen.add(canonical.lower())
        normalized.append(canonical)

        if canonical != skill.strip():
            transformations.append({
                "field": "skill",
                "type": "normalization",
                "before": skill.strip(),
                "after": canonical,
            })

    return normalized, transformations
