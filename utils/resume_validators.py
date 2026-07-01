"""
Resume Validators

Contains logic to validate resume fields, specifically timelines,
dates, and logical consistency.
"""
import logging
from typing import Any, Dict, List
import datetime

logger = logging.getLogger(__name__)

def validate_dates(start_year: int | None, end_year: int | None) -> list[str]:
    """Validate that start year is before end year, etc."""
    warnings = []
    current_year = datetime.datetime.now().year
    
    if start_year and start_year > current_year + 5:
        warnings.append(f"Start year {start_year} seems too far in the future.")
        
    if start_year and end_year:
        if start_year > end_year:
            warnings.append(f"Start year {start_year} is after end year {end_year}.")
            
    return warnings

def validate_experience(entries: List[Dict[str, Any]]) -> List[str]:
    """Validate experience entries."""
    warnings = []
    for idx, entry in enumerate(entries):
        if not entry.get("company"):
            warnings.append(f"Experience entry {idx+1} is missing a company.")
        if not entry.get("title"):
            warnings.append(f"Experience entry {idx+1} is missing a title.")
    return warnings

def validate_education(entries: List[Dict[str, Any]]) -> List[str]:
    """Validate education entries."""
    warnings = []
    for idx, entry in enumerate(entries):
        if not entry.get("institution"):
            warnings.append(f"Education entry {idx+1} is missing an institution.")
            
        start_year = entry.get("start_year")
        end_year = entry.get("end_year")
        
        if start_year:
            try:
                start_year = int(start_year)
            except ValueError:
                start_year = None
                
        if end_year:
            try:
                end_year = int(end_year)
            except ValueError:
                end_year = None
                
        warnings.extend(validate_dates(start_year, end_year))
            
    return warnings

def validate_profile(profile: Dict[str, Any]) -> List[str]:
    """Run all validation rules on a parsed profile."""
    warnings = []
    
    if "experience" in profile and isinstance(profile["experience"], list):
        warnings.extend(validate_experience(profile["experience"]))
        
    if "education" in profile and isinstance(profile["education"], list):
        warnings.extend(validate_education(profile["education"]))
        
    return warnings
