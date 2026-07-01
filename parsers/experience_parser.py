"""
Experience Parser

Splits the experience section text into individual blocks and extracts fields
such as company, title, start date, end date, and description using a heuristic approach.
"""
import re
from typing import Any, Dict, List

# Common date patterns like "Jan 2020 - Present", "2019 to 2021", etc.
DATE_PATTERN = re.compile(
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|\d{4})"
    r"\s*(?:-|–|—|to)\s*"
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|\d{4}|Present|Current|Now)",
    re.IGNORECASE,
)

def parse_experience_section(text: str) -> List[Dict[str, str]]:
    """Parse the raw experience section text into structured entries."""
    entries: List[Dict[str, str]] = []
    lines = text.split("\n")
    
    current_entry: Dict[str, str] = {}
    summary_lines: List[str] = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        date_match = DATE_PATTERN.search(line)
        
        # A new date usually signifies a new job entry
        if date_match:
            if current_entry:
                if summary_lines:
                    current_entry["summary"] = "\n".join(summary_lines).strip()
                entries.append(current_entry)
                
            current_entry = {
                "start": date_match.group(1).strip(),
                "end": date_match.group(2).strip(),
            }
            summary_lines = []
            
            # Remove the date from the line to parse the rest
            remaining = DATE_PATTERN.sub("", line).strip(" |-–—,")
            if remaining:
                _extract_company_title(remaining, current_entry)
                
        elif current_entry:
            # If we don't have a company or title yet, check if this line looks like one
            if not current_entry.get("company") and not current_entry.get("title") and len(line.split()) <= 8:
                _extract_company_title(line, current_entry)
            else:
                summary_lines.append(line)
        else:
            # We found a block before a date string, let's just tentatively start an entry
            current_entry = {}
            if len(line.split()) <= 8:
                _extract_company_title(line, current_entry)
            else:
                summary_lines.append(line)
                
    if current_entry:
        if summary_lines:
            current_entry["summary"] = "\n".join(summary_lines).strip()
        entries.append(current_entry)
        
    return entries

def _extract_company_title(text: str, entry: Dict[str, str]) -> None:
    """Helper to extract company and title from a short line."""
    if "|" in text:
        parts = text.split("|")
        entry["company"] = parts[0].strip()
        if len(parts) > 1:
            entry["title"] = parts[1].strip()
    elif " at " in text.lower():
        parts = re.split(r"\s+at\s+", text, flags=re.IGNORECASE)
        entry["title"] = parts[0].strip()
        if len(parts) > 1:
            entry["company"] = parts[1].strip()
    elif " - " in text or " – " in text:
        parts = re.split(r"\s+[-–]\s+", text)
        entry["company"] = parts[0].strip()
        if len(parts) > 1:
            entry["title"] = parts[1].strip()
    else:
        # Default fallback
        if not entry.get("company"):
            entry["company"] = text
        elif not entry.get("title"):
            entry["title"] = text
