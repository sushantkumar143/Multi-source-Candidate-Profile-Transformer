"""
Semantic Normalizer.

Standardizes companies, titles, degrees, and institutions to make
deduplication and merging highly accurate.
"""
import re
from typing import Any

# Company Suffixes to remove
COMPANY_SUFFIX_RE = re.compile(
    r"\b(llc|ltd|inc|corp|co|corporation|incorporated|limited|pvt|gmbh|saas|solutions|services|systems|technologies|tech)\b\.?",
    re.IGNORECASE
)

# Job Title mappings
TITLE_MAPPINGS = {
    "swe": "Software Engineer",
    "software engineer": "Software Engineer",
    "software developer": "Software Engineer",
    "developer": "Software Engineer",
    "sde": "Software Development Engineer",
    "software development engineer": "Software Development Engineer",
    "fullstack": "Full Stack Developer",
    "full stack": "Full Stack Developer",
    "frontend": "Frontend Engineer",
    "front end": "Frontend Engineer",
    "backend": "Backend Engineer",
    "back end": "Backend Engineer",
    "qa": "QA Engineer",
    "quality assurance": "QA Engineer",
    "data scientist": "Data Scientist",
    "machine learning engineer": "Machine Learning Engineer",
    "ml engineer": "Machine Learning Engineer",
}

# Degree mappings
DEGREE_MAPPINGS = {
    "btech": "B.Tech",
    "b tech": "B.Tech",
    "bachelor of technology": "B.Tech",
    "b.tech": "B.Tech",
    "b.e": "B.E.",
    "be": "B.E.",
    "bachelor of engineering": "B.E.",
    "mtech": "M.Tech",
    "m tech": "M.Tech",
    "master of technology": "M.Tech",
    "m.tech": "M.Tech",
    "m.s": "M.S.",
    "ms": "M.S.",
    "master of science": "M.S.",
    "b.s": "B.S.",
    "bs": "B.S.",
    "bachelor of science": "B.S.",
    "phd": "Ph.D.",
    "ph.d": "Ph.D.",
    "doctorate": "Ph.D.",
    "mba": "M.B.A.",
    "m.b.a": "M.B.A.",
    "master of business administration": "M.B.A.",
}

def normalize_company(name: Any) -> str:
    """Normalize company name by removing suffixes and extra spaces."""
    if not isinstance(name, str):
        return ""
    name_clean = re.sub(r"[,|\-–—]", " ", name)
    # Remove suffixes
    name_clean = COMPANY_SUFFIX_RE.sub("", name_clean.lower())
    # Remove non-alphanumeric chars (except spaces)
    name_clean = re.sub(r"[^\w\s]", "", name_clean)
    return " ".join(name_clean.split()).strip()

def normalize_title(title: Any) -> str:
    """Standardize common job title variations."""
    if not isinstance(title, str):
        return ""
    title_clean = title.strip().lower()
    title_clean = re.sub(r"[^\w\s]", "", title_clean)
    
    # Check for direct mappings
    for k, v in TITLE_MAPPINGS.items():
        if title_clean == k:
            return v
        if title_clean.startswith(k + " ") or title_clean.endswith(" " + k):
            # Replace the keyword in place
            words = title_clean.split()
            # replace the matching part
            mapped = [TITLE_MAPPINGS.get(w, w) for w in words]
            return " ".join(mapped).title()
            
    return title.strip().title()

def normalize_degree(degree: Any) -> str:
    """Standardize degree names."""
    if not isinstance(degree, str):
        return ""
    degree_clean = degree.strip().lower()
    degree_clean = re.sub(r"[^\w\s\.]", "", degree_clean)
    
    # Try exact or partial lookup
    for k, v in DEGREE_MAPPINGS.items():
        if degree_clean == k or degree_clean.replace(".", "") == k.replace(".", ""):
            return v
            
    return degree.strip().title()

def normalize_institution(inst: Any) -> str:
    """Normalize university and college names."""
    if not isinstance(inst, str):
        return ""
    inst_clean = inst.strip().lower()
    # Remove common words like "university", "institute", "of", "and"
    inst_clean = re.sub(r"\b(university|institute|college|of|technology|science|engineering)\b", "", inst_clean)
    inst_clean = re.sub(r"[^\w\s]", "", inst_clean)
    return " ".join(inst_clean.split()).strip()
