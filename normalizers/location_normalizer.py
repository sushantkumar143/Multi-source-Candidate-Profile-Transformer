"""
Location Normalizer.

Normalizes location strings to structured {city, region, country} format.
Country names are normalized to ISO-3166 alpha-2 codes:
- "United States" → "US"
- "India" → "IN"
- "USA" → "US"
- "Bangalore, India" → {city: "Bangalore", region: null, country: "IN"}
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Common country name to ISO-3166 alpha-2 mapping
COUNTRY_MAP: dict[str, str] = {
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "us": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "india": "IN",
    "in": "IN",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "england": "GB",
    "canada": "CA",
    "ca": "CA",
    "germany": "DE",
    "de": "DE",
    "france": "FR",
    "fr": "FR",
    "australia": "AU",
    "au": "AU",
    "japan": "JP",
    "jp": "JP",
    "china": "CN",
    "cn": "CN",
    "brazil": "BR",
    "br": "BR",
    "singapore": "SG",
    "sg": "SG",
    "netherlands": "NL",
    "nl": "NL",
    "ireland": "IE",
    "ie": "IE",
    "israel": "IL",
    "il": "IL",
    "sweden": "SE",
    "se": "SE",
    "switzerland": "CH",
    "ch": "CH",
    "south korea": "KR",
    "kr": "KR",
    "spain": "ES",
    "es": "ES",
    "italy": "IT",
    "it": "IT",
    "mexico": "MX",
    "mx": "MX",
    "russia": "RU",
    "ru": "RU",
    "uae": "AE",
    "united arab emirates": "AE",
    "ae": "AE",
    "new zealand": "NZ",
    "nz": "NZ",
    "poland": "PL",
    "pl": "PL",
    "portugal": "PT",
    "pt": "PT",
    "indonesia": "ID",
    "id": "ID",
    "philippines": "PH",
    "ph": "PH",
    "vietnam": "VN",
    "vn": "VN",
    "thailand": "TH",
    "th": "TH",
    "malaysia": "MY",
    "my": "MY",
    "pakistan": "PK",
    "pk": "PK",
    "bangladesh": "BD",
    "bd": "BD",
    "sri lanka": "LK",
    "lk": "LK",
    "nigeria": "NG",
    "ng": "NG",
    "south africa": "ZA",
    "za": "ZA",
    "kenya": "KE",
    "ke": "KE",
    "egypt": "EG",
    "eg": "EG",
    "argentina": "AR",
    "ar": "AR",
    "colombia": "CO",
    "co": "CO",
    "chile": "CL",
    "cl": "CL",
    "turkey": "TR",
    "tr": "TR",
    "denmark": "DK",
    "dk": "DK",
    "norway": "NO",
    "no": "NO",
    "finland": "FI",
    "fi": "FI",
    "austria": "AT",
    "at": "AT",
    "belgium": "BE",
    "be": "BE",
    "czech republic": "CZ",
    "czechia": "CZ",
    "cz": "CZ",
    "romania": "RO",
    "ro": "RO",
    "hungary": "HU",
    "hu": "HU",
    "ukraine": "UA",
    "ua": "UA",
    "taiwan": "TW",
    "tw": "TW",
    "hong kong": "HK",
    "hk": "HK",
}

# Indian state/city to region mapping
INDIA_REGIONS: dict[str, str] = {
    "bangalore": "Karnataka",
    "bengaluru": "Karnataka",
    "mumbai": "Maharashtra",
    "bombay": "Maharashtra",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "hyderabad": "Telangana",
    "chennai": "Tamil Nadu",
    "madras": "Tamil Nadu",
    "pune": "Maharashtra",
    "kolkata": "West Bengal",
    "calcutta": "West Bengal",
    "ahmedabad": "Gujarat",
    "jaipur": "Rajasthan",
    "lucknow": "Uttar Pradesh",
    "chandigarh": "Chandigarh",
    "gurgaon": "Haryana",
    "gurugram": "Haryana",
    "noida": "Uttar Pradesh",
    "kochi": "Kerala",
    "thiruvananthapuram": "Kerala",
    "indore": "Madhya Pradesh",
    "bhopal": "Madhya Pradesh",
    "coimbatore": "Tamil Nadu",
    "nagpur": "Maharashtra",
    "visakhapatnam": "Andhra Pradesh",
    "patna": "Bihar",
    "goa": "Goa",
}

# US state abbreviations and cities
US_STATES: dict[str, str] = {
    "california": "CA", "ca": "CA",
    "new york": "NY", "ny": "NY",
    "texas": "TX", "tx": "TX",
    "washington": "WA", "wa": "WA",
    "massachusetts": "MA", "ma": "MA",
    "illinois": "IL", "il": "IL",
    "florida": "FL", "fl": "FL",
    "pennsylvania": "PA", "pa": "PA",
    "ohio": "OH", "oh": "OH",
    "georgia": "GA", "ga": "GA",
    "colorado": "CO", "co": "CO",
    "virginia": "VA", "va": "VA",
    "north carolina": "NC", "nc": "NC",
    "oregon": "OR", "or": "OR",
    "michigan": "MI", "mi": "MI",
    "new jersey": "NJ", "nj": "NJ",
    "arizona": "AZ", "az": "AZ",
    "minnesota": "MN", "mn": "MN",
    "maryland": "MD", "md": "MD",
    "tennessee": "TN", "tn": "TN",
    "wisconsin": "WI", "wi": "WI",
    "connecticut": "CT", "ct": "CT",
    "utah": "UT", "ut": "UT",
    "district of columbia": "DC", "dc": "DC",
}


def normalize_location(raw_location: str | dict) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Normalize a location string or dict to {city, region, country} format.

    Args:
        raw_location: Location as a string ("Bangalore, India") or
                     dict ({"city": "Bangalore", "country": "India"}).

    Returns:
        Tuple of:
        - Normalized location dict with ISO-3166 country code
        - List of transformation records for audit
    """
    transformations: list[dict[str, str]] = []

    if isinstance(raw_location, dict):
        city = raw_location.get("city")
        region = raw_location.get("region")
        country = raw_location.get("country", "")
        raw_str = f"{city}, {region}, {country}" if region else f"{city}, {country}"
    elif isinstance(raw_location, str):
        raw_str = raw_location
        city, region, country = _parse_location_string(raw_location)
    else:
        return {"city": None, "region": None, "country": None}, []

    # Normalize country to ISO-3166 alpha-2
    if country:
        country_normalized = _normalize_country(country)
        if country_normalized and country_normalized != country:
            transformations.append({
                "field": "location.country",
                "type": "normalization",
                "before": country,
                "after": country_normalized,
            })
            country = country_normalized

    # Try to determine region
    if city and not region:
        region = _infer_region(city, country)

    result = {
        "city": city.strip().title() if city else None,
        "region": region.strip() if region else None,
        "country": country if country else None,
    }

    return result, transformations


def _parse_location_string(location: str) -> tuple[str | None, str | None, str | None]:
    """Parse a location string into city, region, country.

    Handles formats like:
    - "Bangalore, India"
    - "San Francisco, CA, USA"
    - "New York, NY"
    - "London, UK"
    """
    parts = [p.strip() for p in location.split(",")]

    city = None
    region = None
    country = None

    if len(parts) >= 3:
        city = parts[0]
        region = parts[1]
        country = parts[2]
    elif len(parts) == 2:
        city = parts[0]
        second = parts[1].strip()

        # Check if second part is a country
        if second.lower() in COUNTRY_MAP:
            country = second
        # Check if it's a US state
        elif second.lower() in US_STATES:
            region = US_STATES[second.lower()]
            country = "US"
        elif len(second) == 2 and second.upper() in [v for v in US_STATES.values()]:
            region = second.upper()
            country = "US"
        else:
            # Assume it's a country
            country = second
    elif len(parts) == 1:
        # Could be just a city or a country
        single = parts[0].strip()
        if single.lower() in COUNTRY_MAP:
            country = single
        else:
            city = single

    return city, region, country


def _normalize_country(country: str) -> str | None:
    """Normalize a country name or code to ISO-3166 alpha-2."""
    if not country:
        return None

    country_clean = country.strip()
    lookup = country_clean.lower()

    # Direct lookup
    if lookup in COUNTRY_MAP:
        return COUNTRY_MAP[lookup]

    # Already an alpha-2 code?
    if len(country_clean) == 2 and country_clean.isalpha():
        return country_clean.upper()

    logger.debug("Unknown country: '%s' — keeping as-is", country)
    return country_clean


def _infer_region(city: str, country: str | None) -> str | None:
    """Try to infer region from city name."""
    city_lower = city.strip().lower()

    if country in ("IN", "India", "india"):
        return INDIA_REGIONS.get(city_lower)

    return None
