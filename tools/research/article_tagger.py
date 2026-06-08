"""
Article Tagging Module for News Collection System

This module provides functions to tag articles with geographic and topical information
to help with newsletter curation and article organization.
"""

import re
from typing import List, Dict

# Geographic mapping: cities, countries, regions -> continents
GEOGRAPHIC_MAPPING = {
    # Americas
    "united states": "Americas", "usa": "Americas", "us": "Americas",
    "new york": "Americas", "washington dc": "Americas", "washington d.c.": "Americas",
    "los angeles": "Americas", "san francisco": "Americas", "chicago": "Americas",
    "houston": "Americas", "toronto": "Americas", "mexico city": "Americas",
    "são paulo": "Americas", "sao paulo": "Americas", "buenos aires": "Americas",
    "calgary": "Americas", "austin": "Americas", "portland": "Americas",
    "panama city": "Americas", "san jose": "Americas", "palo alto": "Americas",
    "mountain view": "Americas", "seattle": "Americas", "boston": "Americas",
    "canada": "Americas", "mexico": "Americas", "brazil": "Americas",
    "argentina": "Americas", "chile": "Americas", "colombia": "Americas",
    "peru": "Americas", "venezuela": "Americas", "ecuador": "Americas",
    "bolivia": "Americas", "paraguay": "Americas", "uruguay": "Americas",
    "guyana": "Americas", "suriname": "Americas", "french guiana": "Americas",
    "cuba": "Americas", "jamaica": "Americas", "haiti": "Americas",
    "dominican republic": "Americas", "puerto rico": "Americas",
    "guatemala": "Americas", "honduras": "Americas", "el salvador": "Americas",
    "nicaragua": "Americas", "costa rica": "Americas", "panama": "Americas",
    
    # Europe
    "united kingdom": "Europe", "uk": "Europe", "britain": "Europe",
    "london": "Europe", "paris": "Europe", "berlin": "Europe", "brussels": "Europe",
    "amsterdam": "Europe", "madrid": "Europe", "rome": "Europe", "moscow": "Europe",
    "warsaw": "Europe", "istanbul": "Europe", "kyiv": "Europe", "kiev": "Europe",
    "gibraltar": "Europe", "copenhagen": "Europe", "munich": "Europe",
    "barcelona": "Europe", "aberdeen": "Europe", "stavanger": "Europe",
    "france": "Europe", "germany": "Europe", "italy": "Europe", "spain": "Europe",
    "poland": "Europe", "russia": "Europe", "ukraine": "Europe", "turkey": "Europe",
    "netherlands": "Europe", "belgium": "Europe", "denmark": "Europe",
    "sweden": "Europe", "norway": "Europe", "finland": "Europe",
    "switzerland": "Europe", "austria": "Europe", "czech republic": "Europe",
    "hungary": "Europe", "romania": "Europe", "bulgaria": "Europe",
    "greece": "Europe", "portugal": "Europe", "ireland": "Europe",
    "european union": "Europe", "eu": "Europe",
    
    # Asia
    "china": "Asia", "japan": "Asia", "india": "Asia", "south korea": "Asia",
    "singapore": "Asia", "thailand": "Asia", "indonesia": "Asia",
    "philippines": "Asia", "uae": "Asia", "israel": "Asia",
    "tokyo": "Asia", "beijing": "Asia", "shanghai": "Asia", "hong kong": "Asia",
    "seoul": "Asia", "mumbai": "Asia", "delhi": "Asia", "bangkok": "Asia",
    "jakarta": "Asia", "manila": "Asia", "dubai": "Asia", "tel aviv": "Asia",
    "bangalore": "Asia", "shenzhen": "Asia", "baku": "Asia", "doha": "Asia",
    "kuwait city": "Asia",     "gaza": "Asia", "gaza city": "Asia", "ramallah": "Asia",
    "jerusalem": "Asia", "damascus": "Asia", "beirut": "Asia",
    "palestine": "Asia", "west bank": "Asia", "hamas": "Asia",
    "south asia": "Asia", "southeast asia": "Asia", "middle east": "Asia",
    "asean": "Asia", "gulf states": "Asia", "persian gulf": "Asia",
    "south china sea": "Asia", "east asia": "Asia", "central asia": "Asia",
    # MENA — Asian geography
    "iran": "Asia", "tehran": "Asia",
    "iraq": "Asia", "baghdad": "Asia",
    "saudi arabia": "Asia", "riyadh": "Asia", "jeddah": "Asia",
    "syria": "Asia",
    "yemen": "Asia", "sanaa": "Asia", "aden": "Asia",
    "lebanon": "Asia", "amman": "Asia",
    "jordan": "Asia",
    "qatar": "Asia",
    "bahrain": "Asia", "manama": "Asia",
    "oman": "Asia", "muscat": "Asia",
    "kuwait": "Asia",
    "afghanistan": "Asia", "kabul": "Asia",
    "pakistan": "Asia", "karachi": "Asia", "islamabad": "Asia", "lahore": "Asia",
    
    # Africa
    "egypt": "Africa", "nigeria": "Africa", "south africa": "Africa",
    "kenya": "Africa", "morocco": "Africa", "ethiopia": "Africa",
    "cairo": "Africa", "lagos": "Africa", "johannesburg": "Africa",
    "nairobi": "Africa", "casablanca": "Africa", "addis ababa": "Africa",
    "zimbabwe": "Africa", "harare": "Africa", "bulawayo": "Africa",
    "mutare": "Africa", "gweru": "Africa", "masvingo": "Africa",
    "ghana": "Africa", "accra": "Africa", "kumasi": "Africa",
    "mauritius": "Africa", "port louis": "Africa",
    "democratic republic of congo": "Africa", "drc": "Africa",
    "kinshasa": "Africa", "lubumbashi": "Africa", "goma": "Africa",
    "abuja": "Africa", "dar es salaam": "Africa", "kampala": "Africa",
    "uganda": "Africa", "tanzania": "Africa",
    "north africa": "Africa", "sub-saharan africa": "Africa",
    "west africa": "Africa", "east africa": "Africa", "southern africa": "Africa",
    # North Africa (MENA countries with African geography)
    "libya": "Africa", "tripoli": "Africa", "benghazi": "Africa",
    "tunisia": "Africa", "tunis": "Africa",
    "algeria": "Africa", "algiers": "Africa",
    
    # Oceania
    "australia": "Oceania", "new zealand": "Oceania",
    "sydney": "Oceania", "melbourne": "Oceania", "auckland": "Oceania",
    "wellington": "Oceania", "pacific islands": "Oceania",
    
    # Global/Unclear
    "global": "Global", "worldwide": "Global", "international": "Global",
    "world": "Global", "earth": "Global", "planet": "Global",
    "suez": "Global", "suez canal": "Global",  # Strategic global location
}

# Core topic categories mapping
CORE_TOPICS = {
    "energy": [
        "energy", "electricity", "renewable energy", "solar power", "wind energy",
        "battery storage", "smart grid", "microgrid", "electric vehicles",
        "capacity market", "demand response", "carbon pricing", "carbon tax",
        "feed-in tariff", "grid reliability", "transmission planning",
        "levelized cost of energy", "power purchase agreement", "green bond",
        "esg investment", "coal", "rare earth minerals", "lithium", "nuclear",
        "gas", "oil", "supply chain"
    ],
    "ai": [
        "artificial intelligence", "ai", "machine learning", "ml", "neural network",
        "deep learning", "cybersecurity", "digital twin", "predictive analytics"
    ],
    "blockchain": [
        "blockchain", "cryptocurrency", "bitcoin", "ethereum", "crypto",
        "defi", "web3"
    ],
    "insurance": [
        "insurance", "catastrophe modeling", "exposure data", "reinsurance",
        "underwriting", "climate risk"
    ],
    "geopolitics": [
        "war", "civil unrest", "protest", "climate risk", "conflict",
        "diplomacy", "sanctions", "trade war", "military", "defense",
        "security", "terrorism", "refugees", "migration"
    ]
}

# Maps every location key in GEOGRAPHIC_MAPPING to a canonical country name.
# Entries here override the raw location title-casing so that city mentions
# resolve to the parent country (e.g. "tehran" -> "Iran").
CITY_TO_COUNTRY = {
    # Americas — cities to country
    "new york": "United States", "washington dc": "United States",
    "washington d.c.": "United States", "los angeles": "United States",
    "san francisco": "United States", "chicago": "United States",
    "houston": "United States", "austin": "United States",
    "portland": "United States", "palo alto": "United States",
    "mountain view": "United States", "seattle": "United States",
    "boston": "United States",
    "toronto": "Canada", "calgary": "Canada",
    "mexico city": "Mexico",
    "são paulo": "Brazil", "sao paulo": "Brazil",
    "buenos aires": "Argentina",
    "panama city": "Panama",
    "san jose": "Costa Rica",
    # Europe — cities to country
    "london": "United Kingdom",
    "paris": "France",
    "berlin": "Germany", "munich": "Germany",
    "brussels": "Belgium",
    "amsterdam": "Netherlands",
    "madrid": "Spain", "barcelona": "Spain",
    "rome": "Italy",
    "moscow": "Russia",
    "warsaw": "Poland",
    "istanbul": "Turkey",
    "kyiv": "Ukraine", "kiev": "Ukraine",
    "copenhagen": "Denmark",
    "aberdeen": "United Kingdom",
    "stavanger": "Norway",
    # Asia — cities to country
    "tokyo": "Japan",
    "beijing": "China", "shanghai": "China", "shenzhen": "China",
    "hong kong": "China",
    "seoul": "South Korea",
    "mumbai": "India", "delhi": "India", "bangalore": "India",
    "bangkok": "Thailand",
    "jakarta": "Indonesia",
    "manila": "Philippines",
    "dubai": "UAE",
    "tel aviv": "Israel", "jerusalem": "Israel",
    "baku": "Azerbaijan",
    "gaza": "Palestine", "gaza city": "Palestine", "ramallah": "Palestine",
    # MENA (Asian) — cities to country
    "tehran": "Iran",
    "baghdad": "Iraq",
    "riyadh": "Saudi Arabia", "jeddah": "Saudi Arabia",
    "damascus": "Syria",
    "sanaa": "Yemen", "aden": "Yemen",
    "beirut": "Lebanon",
    "amman": "Jordan",
    "doha": "Qatar",
    "manama": "Bahrain",
    "muscat": "Oman",
    "kuwait city": "Kuwait",
    "kabul": "Afghanistan",
    "karachi": "Pakistan", "islamabad": "Pakistan", "lahore": "Pakistan",
    # Africa — cities to country
    "cairo": "Egypt",
    "lagos": "Nigeria", "abuja": "Nigeria",
    "johannesburg": "South Africa",
    "nairobi": "Kenya",
    "casablanca": "Morocco",
    "addis ababa": "Ethiopia",
    "harare": "Zimbabwe", "bulawayo": "Zimbabwe",
    "mutare": "Zimbabwe", "gweru": "Zimbabwe", "masvingo": "Zimbabwe",
    "accra": "Ghana", "kumasi": "Ghana",
    "port louis": "Mauritius",
    "kinshasa": "Democratic Republic Of Congo",
    "lubumbashi": "Democratic Republic Of Congo",
    "goma": "Democratic Republic Of Congo",
    "dar es salaam": "Tanzania",
    "kampala": "Uganda",
    # North Africa — cities to country
    "tripoli": "Libya", "benghazi": "Libya",
    "tunis": "Tunisia",
    "algiers": "Algeria",
    # Oceania — cities to country
    "sydney": "Australia", "melbourne": "Australia",
    "auckland": "New Zealand", "wellington": "New Zealand",
}

# Countries that appear directly as keys in GEOGRAPHIC_MAPPING (not just cities).
# Used so detect_countries() returns the canonical title-cased country name.
_COUNTRY_KEYS = {
    "united states", "usa", "canada", "mexico", "brazil", "argentina", "chile",
    "colombia", "peru", "venezuela", "ecuador", "bolivia", "paraguay", "uruguay",
    "guyana", "suriname", "french guiana", "cuba", "jamaica", "haiti",
    "dominican republic", "puerto rico", "guatemala", "honduras", "el salvador",
    "nicaragua", "costa rica", "panama",
    "united kingdom", "france", "germany", "italy", "spain", "poland", "russia",
    "ukraine", "turkey", "netherlands", "belgium", "denmark", "sweden", "norway",
    "finland", "switzerland", "austria", "czech republic", "hungary", "romania",
    "bulgaria", "greece", "portugal", "ireland", "european union",
    "china", "japan", "india", "south korea", "singapore", "thailand", "indonesia",
    "philippines", "uae", "israel", "palestine", "azerbaijan",
    "iran", "iraq", "saudi arabia", "syria", "yemen", "lebanon", "jordan",
    "qatar", "bahrain", "oman", "kuwait", "afghanistan", "pakistan",
    "egypt", "nigeria", "south africa", "kenya", "morocco", "ethiopia",
    "zimbabwe", "ghana", "mauritius", "democratic republic of congo",
    "uganda", "tanzania",
    "libya", "tunisia", "algeria",
    "australia", "new zealand",
}


def detect_countries(article_content: str) -> List[str]:
    """
    Extract country/city mentions from article content.

    Args:
        article_content: The full text content of the article

    Returns:
        List of matched countries/cities (e.g., ["United States", "Japan"])
    """
    if not article_content:
        return []

    content_lower = article_content.lower()
    matched_countries = set()

    # Check for geographic mentions using flexible matching
    for location, continent in GEOGRAPHIC_MAPPING.items():
        # Skip generic global terms
        if continent == "Global":
            continue

        # Use word boundary matching for short terms, flexible for longer terms
        if len(location) <= 3:
            # Short terms like "us" need word boundaries to avoid false positives
            pattern = r'\b' + re.escape(location) + r'\b'
        else:
            # Longer terms can use flexible matching
            pattern = re.escape(location)

        if re.search(pattern, content_lower):
            # Resolve city mentions to their parent country when possible
            if location in CITY_TO_COUNTRY:
                matched_countries.add(CITY_TO_COUNTRY[location])
            elif location in _COUNTRY_KEYS:
                matched_countries.add(location.title())
            else:
                matched_countries.add(location.title())

    return sorted(list(matched_countries))

def detect_continents(article_content: str) -> List[str]:
    """
    Extract continent mentions from article content.

    Args:
        article_content: The full text content of the article

    Returns:
        List of continent tags (e.g., ["Asia", "Europe"] or ["Global"])
    """
    if not article_content:
        return ["Unclear"]

    content_lower = article_content.lower()
    continents = set()

    # Check for geographic mentions using flexible matching
    import re
    for location, continent in GEOGRAPHIC_MAPPING.items():
        # Use word boundary matching for short terms, flexible for longer terms
        if len(location) <= 3:
            # Short terms like "us" need word boundaries to avoid false positives
            pattern = r'\b' + re.escape(location) + r'\b'
        else:
            # Longer terms can use flexible matching
            pattern = re.escape(location)

        if re.search(pattern, content_lower):
            continents.add(continent)

    # Handle special cases
    if len(continents) > 1:
        # Multiple continents mentioned - return all continents
        return list(continents)
    elif len(continents) == 1:
        return list(continents)
    else:
        # No clear geographic focus - return Global
        return ["Global"]

def get_matched_keywords(article_content: str, keywords_list: List[str]) -> List[str]:
    """
    Get list of specific keywords that matched the article content.
    
    Args:
        article_content: The full text content of the article
        keywords_list: List of keywords to check against
        
    Returns:
        List of matched keywords
    """
    if not article_content or not keywords_list:
        return []
    
    content_lower = article_content.lower()
    matched_keywords = []
    
    for keyword in keywords_list:
        keyword_lower = keyword.lower()
        # Use word boundary matching for better accuracy
        pattern = r'\b' + re.escape(keyword_lower) + r'\b'
        if re.search(pattern, content_lower):
            matched_keywords.append(keyword)
    
    return matched_keywords

def get_core_topic_categories(matched_keywords: List[str]) -> List[str]:
    """
    Map matched keywords to core topic categories.
    
    Args:
        matched_keywords: List of keywords that matched the article
        
    Returns:
        List of core topic categories
    """
    if not matched_keywords:
        return []
    
    categories = set()
    
    for keyword in matched_keywords:
        keyword_lower = keyword.lower()
        for category, keywords in CORE_TOPICS.items():
            if keyword_lower in [k.lower() for k in keywords]:
                categories.add(category)
    
    return list(categories)

def tag_article(article_content: str, keywords_list: List[str]) -> Dict[str, List[str]]:
    """
    Main function to tag an article with all relevant tags.

    Args:
        article_content: The full text content of the article
        keywords_list: List of keywords to check against

    Returns:
        Dictionary with tagging results:
        {
            'continents': List[str],
            'countries': List[str],
            'matched_keywords': List[str],
            'core_topics': List[str]
        }
    """
    matched_keywords = get_matched_keywords(article_content, keywords_list)

    return {
        'continents': detect_continents(article_content),
        'countries': detect_countries(article_content),
        'matched_keywords': matched_keywords,
        'core_topics': get_core_topic_categories(matched_keywords)
    }

def log_potential_cities(article_content: str) -> None:
    """
    Log potential cities/regions that might be missing from our mapping.
    This helps identify cities to add to the geographic mapping.
    
    Args:
        article_content: The full text content of the article
    """
    # This could be enhanced to actually log to a file or database
    # For now, it's a placeholder for future expansion
    pass