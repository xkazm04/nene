import logging
import re
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup

from .normalizers import DataNormalizerService

logger = logging.getLogger(__name__)

class MetadataExtractorService:
    """Service for extracting specific metadata from infoboxes and content"""
    
    def __init__(self):
        self.normalizer = DataNormalizerService()
    
    def extract_game_metadata(self, infobox) -> Dict[str, Any]:
        """Extract game-specific metadata from infobox"""
        metadata = {}
        
        try:
            rows = infobox.find_all('tr')
            
            for row in rows:
                label_cell = row.find('th')
                value_cell = row.find('td')
                
                if not label_cell or not value_cell:
                    continue
                
                label = label_cell.get_text(strip=True).lower()
                value = value_cell.get_text(separator=' ', strip=True)
                
                # Map infobox fields to our metadata
                if any(key in label for key in ['developer', 'developed']):
                    metadata['description'] = self._clean_text_value(value)
                
                elif any(key in label for key in ['genre', 'type']):
                    metadata['group'] = self.normalizer.normalize_game_genre(value)
                
                elif any(key in label for key in ['release', 'published', 'date']):
                    year = self._extract_year_from_text(value)
                    if year:
                        metadata['item_year'] = year
                
                elif any(key in label for key in ['platform', 'system']):
                    metadata['platforms'] = self._clean_text_value(value)
                
                elif any(key in label for key in ['publisher']):
                    metadata['publisher'] = self._clean_text_value(value)
            
            # Also check for image in infobox
            img = infobox.find('img')
            if img and img.get('src'):
                src = img.get('src')
                if 'upload.wikimedia.org' in src:
                    metadata['image_url'] = self.normalizer.normalize_image_url(src)
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Game infobox extraction failed: {e}")
            return {}
    
    def extract_sports_metadata(self, infobox) -> Dict[str, Any]:
        """Extract sports-specific metadata from infobox"""
        metadata = {}
        
        try:
            rows = infobox.find_all('tr')
            
            for row in rows:
                label_cell = row.find('th')
                value_cell = row.find('td')
                
                if not label_cell or not value_cell:
                    continue
                
                label = label_cell.get_text(strip=True).lower()
                value = value_cell.get_text(separator=' ', strip=True)
                
                if any(key in label for key in ['born', 'birth']):
                    year = self._extract_year_from_text(value)
                    if year:
                        metadata['item_year'] = year
                
                elif any(key in label for key in ['current team', 'club', 'team']):
                    metadata['description'] = self._clean_text_value(value)
                
                elif any(key in label for key in ['position', 'playing position']):
                    metadata['group'] = self._clean_text_value(value)
                
                elif any(key in label for key in ['career', 'active']):
                    years = self._extract_year_range(value)
                    if years and len(years) >= 1:
                        metadata['item_year'] = years[0]
                        if len(years) > 1:
                            metadata['item_year_to'] = years[1]
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Sports infobox extraction failed: {e}")
            return {}
    
    def extract_music_metadata(self, infobox) -> Dict[str, Any]:
        """Extract music-specific metadata from infobox"""
        metadata = {}
        
        try:
            rows = infobox.find_all('tr')
            
            for row in rows:
                label_cell = row.find('th')
                value_cell = row.find('td')
                
                if not label_cell or not value_cell:
                    continue
                
                label = label_cell.get_text(strip=True).lower()
                value = value_cell.get_text(separator=' ', strip=True)
                
                if any(key in label for key in ['genre', 'genres']):
                    metadata['group'] = self.normalizer.normalize_music_genre(value)
                
                elif any(key in label for key in ['formed', 'active', 'career']):
                    year = self._extract_year_from_text(value)
                    if year:
                        metadata['item_year'] = year
                
                elif any(key in label for key in ['label', 'record label']):
                    metadata['description'] = self._clean_text_value(value)
                
                elif any(key in label for key in ['origin', 'location']):
                    metadata['origin'] = self._clean_text_value(value)
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Music infobox extraction failed: {e}")
            return {}
    
    def extract_game_metadata_from_markdown(self, content: str) -> Dict[str, Any]:
        """Extract game metadata from markdown content"""
        metadata = {}
        
        # Multiple patterns for release date
        release_patterns = [
            r'(?:\*\*Release.*?\*\*|Release.*?)\s*[:\|]\s*.*?(\d{4})',
            r'(?:\*\*Released.*?\*\*|Released.*?)\s*[:\|]\s*.*?(\d{4})',
            r'(?:\*\*Publication.*?\*\*|Publication.*?)\s*[:\|]\s*.*?(\d{4})',
            r'(\d{4}).*?(?:release|published)',
            r'Release date.*?(\d{4})'
        ]
        
        for pattern in release_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    metadata['item_year'] = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
        
        # Enhanced developer patterns
        developer_patterns = [
            r'(?:\*\*Developer.*?\*\*|Developer.*?)\s*[:\|]\s*([^\n\|]+)',
            r'(?:\*\*Developed by.*?\*\*|Developed by.*?)\s*[:\|]\s*([^\n\|]+)',
            r'(?:\*\*Studio.*?\*\*|Studio.*?)\s*[:\|]\s*([^\n\|]+)',
            r'Developer(?:\s*\||\s*:|\s*=)\s*([^\n\|]+)'
        ]
        
        for pattern in developer_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                developer = self._clean_text_value(match.group(1))
                if len(developer) > 3 and len(developer) < 100:
                    metadata['description'] = developer
                    break
        
        # Enhanced genre patterns
        genre_patterns = [
            r'(?:\*\*Genre.*?\*\*|Genre.*?)\s*[:\|]\s*([^\n\|]+)',
            r'(?:\*\*Type.*?\*\*|Type.*?)\s*[:\|]\s*([^\n\|]+)',
            r'Genre(?:\s*\||\s*:|\s*=)\s*([^\n\|]+)'
        ]
        
        for pattern in genre_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                genre = self._clean_text_value(match.group(1))
                metadata['group'] = self.normalizer.normalize_game_genre(genre)
                break
        
        return metadata
    
    def extract_sports_metadata_from_markdown(self, content: str) -> Dict[str, Any]:
        """Extract sports metadata from markdown content"""
        metadata = {}
        
        # Birth year patterns
        birth_patterns = [
            r'(?:\*\*Born.*?\*\*|Born.*?)\s*[:\|]\s*.*?(\d{4})',
            r'(?:\*\*Birth.*?\*\*|Birth.*?)\s*[:\|]\s*.*?(\d{4})',
            r'\((\d{4})-',
            r'born.*?(\d{4})'
        ]
        
        for pattern in birth_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    metadata['item_year'] = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
        
        # Team patterns
        team_patterns = [
            r'(?:\*\*Current team.*?\*\*|Current team.*?)\s*[:\|]\s*([^\n\|]+)',
            r'(?:\*\*Club.*?\*\*|Club.*?)\s*[:\|]\s*([^\n\|]+)',
            r'(?:\*\*Team.*?\*\*|Team.*?)\s*[:\|]\s*([^\n\|]+)'
        ]
        
        for pattern in team_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                team = self._clean_text_value(match.group(1))
                if len(team) > 2 and len(team) < 50:
                    metadata['description'] = team
                    break
        
        return metadata
    
    def extract_music_metadata_from_markdown(self, content: str) -> Dict[str, Any]:
        """Extract music metadata from markdown content"""
        metadata = {}
        
        # Formation year patterns
        year_patterns = [
            r'(?:\*\*Formed.*?\*\*|Formed.*?)\s*[:\|]\s*.*?(\d{4})',
            r'(?:\*\*Active.*?\*\*|Active.*?)\s*[:\|]\s*.*?(\d{4})',
            r'(?:\*\*Career.*?\*\*|Career.*?)\s*[:\|]\s*.*?(\d{4})',
            r'\((\d{4})-'
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    metadata['item_year'] = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
        
        # Genre patterns
        genre_patterns = [
            r'(?:\*\*Genre.*?\*\*|Genre.*?)\s*[:\|]\s*([^\n\|]+)',
            r'(?:\*\*Style.*?\*\*|Style.*?)\s*[:\|]\s*([^\n\|]+)'
        ]
        
        for pattern in genre_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                genre = self._clean_text_value(match.group(1))
                metadata['group'] = self.normalizer.normalize_music_genre(genre)
                break
        
        return metadata
    
    def extract_wikipedia_image(self, content: str, url: str) -> Optional[str]:
        """Enhanced image extraction with multiple strategies"""
        
        # Strategy 1: Look for infobox-image class in HTML
        if 'infobox-image' in content:
            soup = BeautifulSoup(content, 'html.parser')
            infobox_img = soup.find('div', class_='infobox-image')
            if infobox_img:
                img = infobox_img.find('img')
                if img and img.get('src'):
                    return self.normalizer.normalize_image_url(img.get('src'))
        
        # Strategy 2: Look for Wikimedia image URLs in content
        image_patterns = [
            r'(https://upload\.wikimedia\.org/[^)\s\]"]+\.(?:jpg|jpeg|png|gif|webp))',
            r'!\[.*?\]\((https://upload\.wikimedia\.org/[^)]+\.(?:jpg|jpeg|png|gif|webp))\)',
            r'src="(https://upload\.wikimedia\.org/[^"]+\.(?:jpg|jpeg|png|gif|webp))"'
        ]
        
        for pattern in image_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return self.normalizer.normalize_image_url(match.group(1))
        
        # Strategy 3: Try to find thumbnail image and convert to full size
        thumb_pattern = r'(https://upload\.wikimedia\.org/[^)\s\]"]+/thumb/[^/]+/[^/]+/[^/]+\.(?:jpg|jpeg|png|gif|webp))'
        match = re.search(thumb_pattern, content, re.IGNORECASE)
        if match:
            thumb_url = match.group(1)
            # Convert thumbnail to full size
            if '/thumb/' in thumb_url:
                parts = thumb_url.split('/thumb/')
                if len(parts) == 2:
                    base_url = parts[0]
                    path_parts = parts[1].split('/')
                    if len(path_parts) >= 2:
                        filename = path_parts[1]
                        full_url = f"{base_url}/{path_parts[0]}/{filename}"
                        return full_url
        
        return None
    
    def _clean_text_value(self, text: str) -> str:
        """Clean text value from infobox"""
        if not text:
            return ""
        
        # Remove extra whitespace and newlines
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common Wikipedia artifacts
        cleaned = re.sub(r'\[.*?\]', '', cleaned)  # Remove [edit] links
        cleaned = re.sub(r'\(.*?\)', '', cleaned)  # Remove parenthetical info
        
        return cleaned.strip()
    
    def _extract_year_from_text(self, text: str) -> Optional[int]:
        """Extract the first reasonable year from text"""
        if not text:
            return None
        
        # Look for 4-digit years
        year_matches = re.findall(r'\b(19|20)\d{2}\b', text)
        
        for year_str in year_matches:
            try:
                year = int(year_str)
                if 1800 <= year <= 2030:  # Reasonable range
                    return year
            except ValueError:
                continue
        
        return None
    
    def _extract_year_range(self, text: str) -> List[int]:
        """Extract year range from text (e.g., '2010-2015' or '2010-present')"""
        years = []
        
        # Look for year ranges
        range_pattern = r'\b(19|20)\d{2}\s*[-–]\s*(?:(19|20)\d{2}|present)\b'
        match = re.search(range_pattern, text, re.IGNORECASE)
        
        if match:
            start_year = int(match.group(0).split('-')[0].strip())
            years.append(start_year)
            
            end_part = match.group(0).split('-')[1].strip().lower()
            if end_part != 'present' and len(end_part) == 4:
                try:
                    end_year = int(end_part)
                    years.append(end_year)
                except ValueError:
                    pass
        
        return years