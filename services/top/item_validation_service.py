import logging
import re
from typing import Dict, Any, List
from difflib import SequenceMatcher
from unidecode import unidecode
from models.top_models.enums import CategoryEnum
from models.top import ItemResponse
from config.database_top import supabase

logger = logging.getLogger(__name__)

class ItemValidationService:
    """Service for validating items and checking duplicates"""
    
    def __init__(self):
        # Minimum similarity threshold for duplicate detection
        self.similarity_threshold = 0.8
        self.exact_match_threshold = 0.95
        
        # Category-specific validation rules
        self.category_rules = {
            CategoryEnum.games: {
                'min_name_length': 2,
                'max_name_length': 150,
                'valid_subcategories': ['video_games', 'board_games', 'mobile_games'],
                'required_fields': ['name', 'category', 'subcategory']
            },
            CategoryEnum.sports: {
                'min_name_length': 2,
                'max_name_length': 100,
                'valid_subcategories': ['soccer', 'basketball', 'hockey', 'tennis', 'golf', 'baseball'],
                'required_fields': ['name', 'category', 'subcategory']
            },
            CategoryEnum.music: {
                'min_name_length': 1,
                'max_name_length': 200,
                'valid_subcategories': ['artists', 'albums', 'songs'],
                'required_fields': ['name', 'category', 'subcategory']
            }
        }
    
    async def validate_item_request(
        self, 
        name: str, 
        category: CategoryEnum, 
        subcategory: str
    ) -> Dict[str, Any]:
        """
        Validate basic item request data
        """
        errors = []
        
        try:
            # Basic name validation
            if not name or not name.strip():
                errors.append("Item name cannot be empty")
            elif len(name.strip()) < 1:
                errors.append("Item name too short")
            elif len(name.strip()) > 255:
                errors.append("Item name too long (max 255 characters)")
            
            # Category-specific validation
            if category in self.category_rules:
                rules = self.category_rules[category]
                
                # Name length rules
                if len(name.strip()) < rules['min_name_length']:
                    errors.append(f"Name too short for {category.value} (min {rules['min_name_length']} characters)")
                elif len(name.strip()) > rules['max_name_length']:
                    errors.append(f"Name too long for {category.value} (max {rules['max_name_length']} characters)")
                
                # Subcategory validation
                if subcategory not in rules['valid_subcategories']:
                    errors.append(f"Invalid subcategory '{subcategory}' for {category.value}. Valid options: {', '.join(rules['valid_subcategories'])}")
            
            # Character validation
            if not self._is_valid_name_format(name):
                errors.append("Item name contains invalid characters")
            
            # Profanity/inappropriate content check (basic)
            if self._contains_inappropriate_content(name):
                errors.append("Item name contains inappropriate content")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Validation error for {name}: {e}")
            return {
                'is_valid': False,
                'errors': [f"Validation failed: {str(e)}"]
            }
    
    async def check_duplicates(
        self, 
        name: str, 
        category: CategoryEnum, 
        subcategory: str
    ) -> Dict[str, Any]:
        """
        Check for duplicate items in the database
        """
        try:
            # Get all items in the same category/subcategory
            query = supabase.table('items').select('*').eq('category', category.value)
            
            if subcategory:
                query = query.eq('subcategory', subcategory)
            
            result = query.execute()
            
            if not result.data:
                return {
                    'is_duplicate': False,
                    'duplicate_count': 0,
                    'existing_items': [],
                    'similarity_scores': [],
                    'exact_match': False
                }
            
            # Check for duplicates using fuzzy matching
            duplicates = []
            similarity_scores = []
            exact_match = False
            
            cleaned_input_name = self._clean_name_for_comparison(name)
            
            for item in result.data:
                existing_name = item.get('name', '')
                cleaned_existing_name = self._clean_name_for_comparison(existing_name)
                
                # Calculate similarity
                similarity = self._calculate_similarity(cleaned_input_name, cleaned_existing_name)
                
                # Check for exact match
                if similarity >= self.exact_match_threshold:
                    exact_match = True
                
                # Add to duplicates if above threshold
                if similarity >= self.similarity_threshold:
                    # Convert to ItemResponse model
                    item_response = ItemResponse(
                        id=item['id'],
                        name=item['name'],
                        category=CategoryEnum(item['category']),
                        subcategory=item.get('subcategory'),
                        description=item.get('description'),
                        item_year=item.get('item_year'),
                        image_url=item.get('image_url'),
                        reference_url=item.get('reference_url'),
                        view_count=item.get('view_count', 0),
                        selection_count=item.get('selection_count', 0),
                        created_at=item['created_at'],
                        updated_at=item['updated_at'],
                        accolades=[],  # Don't load accolades for duplicate check
                        tags=[]       # Don't load tags for duplicate check
                    )
                    
                    duplicates.append(item_response)
                    similarity_scores.append(similarity)
            
            # Sort by similarity score (highest first)
            if duplicates:
                sorted_pairs = sorted(zip(duplicates, similarity_scores), key=lambda x: x[1], reverse=True)
                duplicates, similarity_scores = zip(*sorted_pairs)
                duplicates = list(duplicates)
                similarity_scores = list(similarity_scores)
            
            return {
                'is_duplicate': len(duplicates) > 0,
                'duplicate_count': len(duplicates),
                'existing_items': duplicates[:5],  # Return top 5 most similar
                'similarity_scores': similarity_scores[:5],
                'exact_match': exact_match
            }
            
        except Exception as e:
            logger.error(f"Duplicate check error for {name}: {e}")
            return {
                'is_duplicate': False,
                'duplicate_count': 0,
                'existing_items': [],
                'similarity_scores': [],
                'exact_match': False,
                'error': str(e)
            }
    
    def _clean_name_for_comparison(self, name: str) -> str:
        """Clean name for comparison by removing special chars, normalizing case, etc."""
        if not name:
            return ""
        
        # Convert to ASCII to handle unicode characters
        cleaned = unidecode(name)
        
        # Remove special characters and extra spaces
        cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Convert to lowercase and strip
        cleaned = cleaned.lower().strip()
        
        # Remove common articles and words that don't affect uniqueness
        remove_words = ['the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for']
        words = cleaned.split()
        words = [word for word in words if word not in remove_words]
        
        return ' '.join(words)
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names using sequence matching"""
        if not name1 or not name2:
            return 0.0
        
        # Use SequenceMatcher for fuzzy string matching
        return SequenceMatcher(None, name1, name2).ratio()
    
    def _is_valid_name_format(self, name: str) -> bool:
        """Check if name format is valid"""
        if not name:
            return False
        
        # Check for minimum valid characters (letters, numbers, basic punctuation)
        if not re.search(r'[a-zA-Z0-9]', name):
            return False
        
        # Check for excessive special characters
        special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s\-_:.]', name)) / len(name)
        if special_char_ratio > 0.3:  # More than 30% special characters
            return False
        
        return True
    
    def _contains_inappropriate_content(self, name: str) -> bool:
        """Basic check for inappropriate content"""
        # This is a basic implementation - in production you'd use a more sophisticated filter
        inappropriate_words = [
            'spam', 'test123', 'asdf', 'qwerty', 'admin', 'null', 'undefined'
        ]
        
        name_lower = name.lower()
        return any(word in name_lower for word in inappropriate_words)

# Create service instance
item_validation_service = ItemValidationService()