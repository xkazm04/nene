from typing import Optional
from models.top_models.enums import CategoryEnum
class MetadataPromptBuilder:
    """Specialized prompt builder for item metadata research"""
    
    @staticmethod
    def build_metadata_prompt(name: str, category: CategoryEnum, subcategory: str, user_context: Optional[str] = None) -> str:
        """Build optimized prompt for metadata extraction"""
        
        prompts = {
            'games': {
                'video_games': f"""
Extract metadata for the video game: "{name}"

Provide accurate information in JSON format:
{{
    "description": "Primary developer/publisher name",
    "group": "Main genre (Action, RPG, Strategy, Simulation, Sports, Racing, Puzzle, Platform, Fighting, Shooter, Horror, Indie, MMO, MOBA)",
    "item_year": "Release year (integer)",
    "platforms": ["PC", "PlayStation", "Xbox", "Nintendo", "Mobile"],
    "developer": "Developer studio name",
    "publisher": "Publisher name",
    "engine": "Game engine if known"
}}

Focus on factual data. Use null for unknown fields.
"""
            },
            'sports': {
                'soccer': f"""
Extract metadata for the soccer player: "{name}"

Provide accurate information in JSON format:
{{
    "description": "Current or most famous team",
    "group": "Player type (Club Player, International Player, Manager)",
    "item_year": "Career start year or birth year",
    "item_year_to": "Career end year (null if active)",
    "position": "Playing position",
    "nationality": "Country of origin",
    "teams": ["team1", "team2", "team3"]
}}
"""
            },
            'music': {
                'artists': f"""
Extract metadata for the music artist: "{name}"

Provide accurate information in JSON format:
{{
    "description": "Record label or band type",
    "group": "Primary genre (Pop, Rock, Hip-Hop, Electronic, Classical, Jazz, Country, R&B, Folk)",
    "item_year": "Career start year",
    "item_year_to": "Career end year (null if active)",
    "origin": "Country/city of origin",
    "labels": ["label1", "label2"],
    "members": "Number of members if band"
}}
"""
            }
        }
        
        # Get category-specific prompt
        category_prompts = prompts.get(category.value, {})
        prompt = category_prompts.get(subcategory, f"""
Extract metadata for the {category.value} item: "{name}" in category "{subcategory}"

Provide information in JSON format:
{{
    "description": "Relevant description",
    "group": "Category or type",
    "item_year": "Relevant year",
    "item_year_to": "End year if applicable"
}}
""")
        
        if user_context:
            prompt += f"\n\nAdditional context: {user_context}"
        
        prompt += "\n\nReturn ONLY the JSON object. Be factual and use null for uncertain data."
        
        return prompt