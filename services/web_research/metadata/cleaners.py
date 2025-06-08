import logging
from typing import Dict, Any
from datetime import datetime

from .normalizers import DataNormalizerService

logger = logging.getLogger(__name__)

class DataCleanerService:
    """Service for cleaning and validating extracted metadata"""
    
    def __init__(self):
        self.normalizer = DataNormalizerService()
    
    def clean_metadata(self, metadata: Dict[str, Any], category: str, subcategory: str) -> Dict[str, Any]:
        """Clean and validate extracted metadata"""
        cleaned = {}
        
        for key, value in metadata.items():
            if key.startswith('_'):  # Keep internal metadata
                cleaned[key] = value
                continue
            
            if value is None or value == "":
                continue
            
            # Clean based on field type
            cleaned_value = self._clean_field(key, value, category, subcategory)
            
            if cleaned_value is not None:
                cleaned[key] = cleaned_value
        
        return cleaned
    
    def _clean_field(self, field_name: str, value: Any, category: str, subcategory: str) -> Any:
        """Clean individual field based on its type and category"""
        
        if field_name in ['description']:
            return self._clean_description_field(value, category)
        
        elif field_name in ['group']:
            return self._clean_group_field(value, category, subcategory)
        
        elif field_name in ['item_year', 'item_year_to']:
            return self._clean_year_field(value)
        
        elif field_name == 'image_url':
            return self._clean_image_url_field(value)
        
        elif field_name == 'reference_url':
            return self._clean_reference_url_field(value)
        
        else:
            # For other fields, basic cleaning
            return self._clean_generic_field(value)
    
    def _clean_description_field(self, value: Any, category: str) -> str:
        """Clean description field"""
        if not isinstance(value, str):
            value = str(value)
        
        # Normalize text length and format
        cleaned = self.normalizer.normalize_text_length(value, max_length=500)
        
        # Category-specific validation
        if category == 'games':
            # For games, description should be developer/studio
            if len(cleaned) < 2 or len(cleaned) > 200:
                return None
        elif category == 'sports':
            # For sports, description should be team/club
            if len(cleaned) < 2 or len(cleaned) > 100:
                return None
        elif category == 'music':
            # For music, description could be label/origin
            if len(cleaned) < 2 or len(cleaned) > 150:
                return None
        
        return cleaned if cleaned.strip() else None
    
    def _clean_group_field(self, value: Any, category: str, subcategory: str) -> str:
        """Clean group field with category-specific normalization"""
        if not isinstance(value, str):
            value = str(value)
        
        cleaned = value.strip()
        
        # Apply category-specific normalization
        if category == 'games':
            cleaned = self.normalizer.normalize_game_genre(cleaned)
        elif category == 'music':
            cleaned = self.normalizer.normalize_music_genre(cleaned)
        else:
            cleaned = self.normalizer.normalize_text_length(cleaned, max_length=50)
        
        # Validate length
        if len(cleaned) < 2 or len(cleaned) > 50:
            return None
        
        return cleaned
    
    def _clean_year_field(self, value: Any) -> int:
        """Clean year field with validation"""
        normalized_year = self.normalizer.normalize_year(value)
        
        if normalized_year is None:
            return None
        
        # Additional validation
        current_year = datetime.now().year
        if 1800 <= normalized_year <= current_year + 2:
            return normalized_year
        
        return None
    
    def _clean_image_url_field(self, value: Any) -> str:
        """Clean image URL field"""
        if not isinstance(value, str):
            return None
        
        # Must be from Wikimedia
        if 'wikimedia.org' not in value:
            return None
        
        # Normalize the URL
        cleaned_url = self.normalizer.normalize_image_url(value)
        
        # Basic URL validation
        if not cleaned_url.startswith('https://'):
            return None
        
        # Check for valid image extension
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        if not any(ext in cleaned_url.lower() for ext in valid_extensions):
            return None
        
        return cleaned_url
    
    def _clean_reference_url_field(self, value: Any) -> str:
        """Clean reference URL field"""
        if not isinstance(value, str):
            return None
        
        # Must be from Wikipedia
        if 'wikipedia.org' not in value:
            return None
        
        # Basic URL validation
        if not value.startswith('https://'):
            return None
        
        return value
    
    def _clean_generic_field(self, value: Any) -> Any:
        """Generic field cleaning"""
        if isinstance(value, str):
            cleaned = value.strip()
            
            # Remove if too short or too long
            if len(cleaned) < 1 or len(cleaned) > 1000:
                return None
            
            return cleaned
        
        return value
    
    def validate_metadata_completeness(self, metadata: Dict[str, Any], category: str) -> Dict[str, Any]:
        """Validate metadata completeness and add quality score"""
        
        # Define required and optional fields by category
        required_fields = {
            'games': ['item_year'],
            'sports': ['item_year'],
            'music': ['item_year']
        }
        
        desirable_fields = {
            'games': ['description', 'group', 'image_url'],
            'sports': ['description', 'group'],
            'music': ['description', 'group']
        }
        
        enhancement_fields = ['reference_url', 'image_url']
        
        # Calculate completeness score
        category_required = required_fields.get(category, [])
        category_desirable = desirable_fields.get(category, [])
        
        required_score = sum(1 for field in category_required if metadata.get(field)) / max(len(category_required), 1)
        desirable_score = sum(1 for field in category_desirable if metadata.get(field)) / max(len(category_desirable), 1)
        enhancement_score = sum(1 for field in enhancement_fields if metadata.get(field)) / len(enhancement_fields)
        
        # Overall quality score (0-100)
        quality_score = int((required_score * 0.5 + desirable_score * 0.3 + enhancement_score * 0.2) * 100)
        
        # Add quality metadata
        metadata['_quality_score'] = quality_score
        metadata['_required_fields_present'] = [field for field in category_required if metadata.get(field)]
        metadata['_missing_fields'] = [field for field in category_required + category_desirable if not metadata.get(field)]
        
        return metadata