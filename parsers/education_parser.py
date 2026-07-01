"""
Education Parser

Splits the education section text into individual blocks and extracts fields
such as institution, degree, field of study, and dates.
"""
import re
from typing import Any, Dict, List

DEGREE_PATTERNS = [
    r"(?:B\.?(?:Tech|S|Sc|E|A|Com)\b|Bachelor(?:'s)?(?:\s+of\s+[A-Za-z\s]+)?)",
    r"(?:M\.?(?:Tech|S|Sc|E|A|Com|BA)\b|Master(?:'s)?(?:\s+of\s+[A-Za-z\s]+)?)",
    r"(?:Ph\.?D\.?|Doctorate)",
    r"(?:High School|Secondary|XII|X|Diploma)"
]
DEGREE_RE = re.compile("|".join(DEGREE_PATTERNS), re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")

def parse_education_section(text: str) -> List[Dict[str, Any]]:
    """Parse the raw education section text into structured entries."""
    entries: List[Dict[str, Any]] = []
    lines = text.split("\n")
    
    current_entry: Dict[str, Any] = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        degree_match = DEGREE_RE.search(line)
        year_match = YEAR_RE.search(line)
        
        # If we see a new degree or year, it might be a new entry
        if degree_match or year_match:
            if current_entry and current_entry.get("institution"):
                if (degree_match and current_entry.get("degree")) or (year_match and (current_entry.get("end_year") or current_entry.get("start_year"))):
                    entries.append(current_entry)
                    current_entry = {}
                    
            if degree_match:
                current_entry["degree"] = degree_match.group(0).strip()
                
            if year_match:
                years = YEAR_RE.findall(line)
                if "since" in line.lower() or "present" in line.lower() or "current" in line.lower():
                    current_entry["start_year"] = int(years[0])
                    current_entry["end_year"] = None
                elif len(years) >= 2:
                    current_entry["start_year"] = int(years[0])
                    current_entry["end_year"] = int(years[-1])
                else:
                    # Single year is usually graduation year
                    if "start" in line.lower():
                        current_entry["start_year"] = int(years[0])
                    else:
                        current_entry["end_year"] = int(years[0])
                        
            # Try to extract institution and field
            remaining = line
            if degree_match:
                remaining = remaining[: degree_match.start()] + remaining[degree_match.end() :]
            remaining = re.sub(r"\d{4}", "", remaining)
            remaining = remaining.strip(" ,|-–—")
            
            parts = re.split(r"[,|–—]", remaining)
            parts = [p.strip() for p in parts if p.strip()]
            
            if parts:
                if not current_entry.get("institution"):
                    current_entry["institution"] = parts[0]
                if len(parts) > 1 and not current_entry.get("field"):
                    # We might have a field
                    if " in " in line.lower() and degree_match:
                        field_part = line[line.lower().find(" in ") + 4:]
                        field_part = re.split(r"[,|–—]", field_part)[0].strip()
                        current_entry["field"] = field_part
                    else:
                        current_entry["field"] = parts[1]
                        
        elif not current_entry.get("institution") and len(line.split()) >= 2:
            current_entry["institution"] = line
            
    if current_entry and current_entry.get("institution"):
        entries.append(current_entry)
        
    return entries
