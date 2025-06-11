"""
Prompts for item research using Gemini API
"""

def get_sports_prompt(name: str, category: str, subcategory: str) -> str:
    """Get research prompt for sports players"""
    return f"""
Please research the following FAMOUS sports player and provide their metadata:
Name: "{name}"
Category: {category} - {subcategory}

This person should be a well-known professional athlete. Please search for information and provide ONLY a clean JSON object:

{{
    "status": "success",
    "item_year": "1987",
    "item_year_to": "2024",
    "reference_url": "https://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
    "image_url": "https://upload.wikimedia.org/wikipedia/commons/example.jpg",
    "group": "Professional"
}}

For sports players:
- item_year should be their birth year or career start year
- item_year_to should be current year if still active, or retirement year
- group should be their most famous team or national team
- Find their Wikipedia page and real image URL if possible

IMPORTANT: 
- Return ONLY valid JSON without any comments, explanations, or markdown formatting
- If you cannot find ANY information about this person, return: {{"status": "failed"}}
- But try your best to find information about this athlete first
"""

def get_games_prompt(name: str, category: str, subcategory: str) -> str:
    """Get research prompt for video games"""
    return f"""
Please research the following video game and provide its metadata:
Name: "{name}"
Category: {category} - {subcategory}

Please provide ONLY a clean JSON object:

{{
    "status": "success",
    "item_year": "2011",
    "reference_url": "https://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
    "image_url": "https://upload.wikimedia.org/wikipedia/en/example.jpg",
    "group": "Action role-playing"
}}

For games:
- item_year should be release year
- group should be the game genre from this list: Shooter, cRPG, jRPG, Action, Sports, MOBA, Mech, RPG, Horror, Fighting, Royale, Strategy, Adventure, MMORPG, RTS, Hero Shooter, Metroidvania, Stealth, Puzzle, Sandbox, Rogue, Souls, Survival, Card

IMPORTANT: Return ONLY valid JSON without any comments, explanations, or markdown formatting.
"""

def get_music_prompt(name: str, category: str, subcategory: str) -> str:
    """Get research prompt for music artists/bands"""
    return f"""
Please research the following music artist/band and provide their metadata:
Name: "{name}"
Category: {category} - {subcategory}

Please provide ONLY a clean JSON object:

{{
    "status": "success",
    "item_year": "1975",
    "item_year_to": "2023",
    "reference_url": "https://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
    "image_url": "https://upload.wikimedia.org/wikipedia/commons/example.jpg",
    "group": "Rock"
}}

For music:
- item_year should be career start or formation year
- item_year_to should be current year if active, or end year if disbanded
- group should be music genre from: Rock, Pop, Hip Hop, Jazz, Classical, Electronic, Country, Blues, R&B, Folk, Reggae, Punk, Metal, Alternative, Indie, Soul, Funk, Disco, House, Techno

IMPORTANT: Return ONLY valid JSON without any comments, explanations, or markdown formatting.
"""

def get_generic_prompt(name: str, category: str, subcategory: str) -> str:
    """Get generic research prompt for other categories"""
    return f"""
Please research the following item and provide its metadata:
Name: "{name}"
Category: {category} - {subcategory}

Please provide ONLY a clean JSON object:

{{
    "status": "success",
    "item_year": "2000",
    "item_year_to": "2023",
    "reference_url": "https://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
    "image_url": "https://upload.wikimedia.org/wikipedia/commons/example.jpg",
    "group": "General"
}}

IMPORTANT: Return ONLY valid JSON without any comments, explanations, or markdown formatting.
"""

def get_research_prompt(name: str, category: str, subcategory: str) -> str:
    """Get appropriate prompt based on category"""
    category_lower = category.lower()
    
    if category_lower == 'sports':
        return get_sports_prompt(name, category, subcategory)
    elif category_lower == 'games':
        return get_games_prompt(name, category, subcategory)
    elif category_lower == 'music':
        return get_music_prompt(name, category, subcategory)
    else:
        return get_generic_prompt(name, category, subcategory)