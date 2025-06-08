import logging

logger = logging.getLogger(__name__)

class DataNormalizerService:
    """Service for normalizing and standardizing extracted data"""
    
    def __init__(self):
        self.game_genre_mapping = {
            'action': 'Action',
            'adventure': 'Adventure',
            'role-playing': 'RPG',
            'rpg': 'RPG',
            'strategy': 'Strategy',
            'real-time strategy': 'Strategy',
            'turn-based strategy': 'Strategy',
            'simulation': 'Simulation',
            'sports': 'Sports',
            'racing': 'Racing',
            'puzzle': 'Puzzle',
            'platform': 'Platform',
            'platformer': 'Platform',
            'fighting': 'Fighting',
            'shooter': 'Shooter',
            'first-person shooter': 'Shooter',
            'third-person shooter': 'Shooter',
            'horror': 'Horror',
            'indie': 'Indie',
            'mmo': 'MMO',
            'moba': 'MOBA',
            'survival': 'Survival'
        }
        
        self.music_genre_mapping = {
            'pop': 'Pop',
            'rock': 'Rock',
            'hip-hop': 'Hip-Hop',
            'hip hop': 'Hip-Hop',
            'electronic': 'Electronic',
            'classical': 'Classical',
            'jazz': 'Jazz',
            'country': 'Country',
            'r&b': 'R&B',
            'folk': 'Folk',
            'blues': 'Blues',
            'metal': 'Metal',
            'heavy metal': 'Metal',
            'alternative': 'Alternative',
            'indie': 'Indie'
        }
    
    def normalize_game_genre(self, genre: str) -> str:
        """Normalize game genre to standard categories"""
        if not genre:
            return genre
        
        genre_lower = genre.lower()
        
        # Try exact matches first
        for key, value in self.game_genre_mapping.items():
            if key == genre_lower:
                return value
        
        # Try partial matches
        for key, value in self.game_genre_mapping.items():
            if key in genre_lower:
                return value
        
        # Return cleaned original if no mapping
        return self._clean_text_for_display(genre)
    
    def normalize_music_genre(self, genre: str) -> str:
        """Normalize music genre to standard categories"""
        if not genre:
            return genre
        
        genre_lower = genre.lower()
        
        for key, value in self.music_genre_mapping.items():
            if key in genre_lower:
                return value
        
        return self._clean_text_for_display(genre)
    
    def normalize_image_url(self, url: str) -> str:
        """Normalize image URL to ensure it's accessible"""
        if not url:
            return url
        
        # Ensure HTTPS
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = 'https://upload.wikimedia.org' + url
        
        # Remove thumbnail path to get original image
        if '/thumb/' in url:
            parts = url.split('/thumb/')
            if len(parts) == 2:
                base_url = parts[0]
                path_parts = parts[1].split('/')
                if len(path_parts) >= 2:
                    filename = path_parts[1]
                    url = f"{base_url}/{path_parts[0]}/{filename}"
        
        return url
    
    def normalize_year(self, year_value) -> int:
        """Normalize year value to integer with validation"""
        try:
            if isinstance(year_value, str):
                # Extract first 4-digit year from string
                import re
                year_match = re.search(r'\b(19|20)\d{2}\b', year_value)
                if year_match:
                    year = int(year_match.group(0))
                else:
                    return None
            elif isinstance(year_value, (int, float)):
                year = int(year_value)
            else:
                return None
            
            # Validate year range
            if 1800 <= year <= 2030:
                return year
            else:
                return None
                
        except (ValueError, TypeError):
            return None
    
    def normalize_text_length(self, text: str, max_length: int = 500) -> str:
        """Normalize text length and clean formatting"""
        if not text:
            return ""
        
        cleaned = self._clean_text_for_display(text)
        
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length].rsplit(' ', 1)[0] + '...'
        
        return cleaned
    
    def _clean_text_for_display(self, text: str) -> str:
        """Clean text for display purposes"""
        if not text:
            return ""
        
        import re
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove Wikipedia markup
        cleaned = re.sub(r'\[.*?\]', '', cleaned)  # Remove [edit] links
        cleaned = re.sub(r'\{.*?\}', '', cleaned)  # Remove template markup
        
        # Clean up parenthetical information (keep short ones)
        def clean_parentheses(match):
            content = match.group(1)
            if len(content) < 20:  # Keep short parenthetical info
                return f"({content})"
            return ""
        
        cleaned = re.sub(r'\(([^)]+)\)', clean_parentheses, cleaned)
        
        # Final cleanup
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned