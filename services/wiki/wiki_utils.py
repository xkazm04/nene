"""
Utility functions for item processing
"""
import json
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def clean_json_response(text: str) -> str:
    """Clean JSON response by removing comments and markdown formatting"""
    # Remove markdown code block markers
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = text.strip()
    
    # Remove // comments from JSON
    # This regex matches // comments but not URLs (which have //)
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Find // that are not part of URLs
        # Look for // that are not preceded by http: or https:
        comment_match = re.search(r'(?<!:)//.*$', line)
        if comment_match:
            # Remove the comment part
            line = line[:comment_match.start()].rstrip()
            # Remove trailing comma if it exists after removing comment
            line = re.sub(r',\s*$', '', line)
        cleaned_lines.append(line)
    
    # Join lines back
    cleaned_text = '\n'.join(cleaned_lines)
    
    # Remove any trailing commas before closing braces/brackets
    cleaned_text = re.sub(r',(\s*[}\]])', r'\1', cleaned_text)
    
    return cleaned_text.strip()

def manual_json_extraction(text: str) -> Optional[Dict[str, Any]]:
    """Manually extract data from JSON-like text when parsing fails"""
    try:
        data = {}
        
        # Extract key patterns
        patterns = {
            'status': r'"status":\s*"([^"]*)"',
            'item_year': r'"item_year":\s*"([^"]*)"',
            'item_year_to': r'"item_year_to":\s*"([^"]*)"',
            'reference_url': r'"reference_url":\s*"([^"]*)"',
            'image_url': r'"image_url":\s*"([^"]*)"',
            'group': r'"group":\s*"([^"]*)"',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data[key] = match.group(1)
        
        if data and 'status' in data:
            logger.info("Manual extraction successful")
            return data
        else:
            logger.warning("Manual extraction failed - no status found")
            return None
            
    except Exception as e:
        logger.error(f"Manual extraction error: {e}")
        return None

def extract_json_from_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON from Gemini response with improved error handling"""
    try:
        logger.info(f"Raw response preview: {response_text[:100]}...")
        
        # Clean the response
        cleaned_text = clean_json_response(response_text)
        logger.info(f"Cleaned text preview: {cleaned_text[:100]}...")
        
        # Method 1: Try to parse the cleaned text directly
        try:
            data = json.loads(cleaned_text)
            logger.info("Successfully parsed JSON (direct method)")
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"Direct parsing failed: {e}")
        
        # Method 2: Extract JSON blocks with better logic
        json_blocks = []
        brace_count = 0
        start_pos = -1
        
        for i, char in enumerate(cleaned_text):
            if char == '{':
                if brace_count == 0:
                    start_pos = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_pos != -1:
                    json_block = cleaned_text[start_pos:i+1]
                    json_blocks.append(json_block)
                    start_pos = -1
        
        # Try to parse each JSON block
        for json_block in json_blocks:
            try:
                # Additional cleaning for the specific block
                json_block = re.sub(r',(\s*[}\]])', r'\1', json_block)  # Remove trailing commas
                data = json.loads(json_block)
                logger.info("Successfully parsed JSON (block method)")
                return data
            except json.JSONDecodeError as e:
                logger.warning(f"Block parsing failed: {e}")
                continue
        
        # Method 3: Try to manually extract key-value pairs if JSON parsing fails
        logger.warning("Attempting manual extraction...")
        return manual_json_extraction(cleaned_text)
        
    except Exception as e:
        logger.error(f"Error in JSON extraction: {e}")
        return None

def get_columns_to_update(existing_item: Dict[str, Any], research_data: Dict[str, Any]) -> Dict[str, Any]:
    """Determine which columns need to be updated"""
    updates = {}
    
    # Define mappings between research data and database columns
    field_mappings = {
        'item_year': 'item_year',
        'item_year_to': 'item_year_to',
        'reference_url': 'reference_url',
        'image_url': 'image_url',
        'group': 'group'
    }
    
    for research_field, db_field in field_mappings.items():
        if research_field in research_data and research_data[research_field]:
            existing_value = existing_item.get(db_field)
            
            # Special handling for sports category - always update group field
            if existing_item.get('category') == 'sports' and db_field == 'group':
                updates[db_field] = research_data[research_field]
                if existing_value and existing_value != research_data[research_field]:
                    logger.info(f"Updating {db_field} for sports: '{existing_value}' → '{research_data[research_field]}'")
                else:
                    logger.info(f"Setting {db_field} for sports: {research_data[research_field]}")
            
            # Standard handling for other fields - only update if empty/null
            elif not existing_value or existing_value == '' or existing_value is None:
                updates[db_field] = research_data[research_field]
                logger.info(f"Will update {db_field}: {research_data[research_field]}")
            else:
                logger.info(f"Skipping {db_field} - already has value: {existing_value}")
    
    return updates

def validate_item_data(item: Dict[str, Any]) -> tuple[bool, str]:
    """Validate item data structure"""
    name = item.get('name', '').strip()
    category = item.get('category', '').strip()
    
    if not name:
        return False, "Missing required field: name"
    
    if not category:
        return False, "Missing required field: category"
    
    if category not in ['sports', 'games', 'music']:
        return False, f"Invalid category: {category}. Must be one of: sports, games, music"
    
    return True, "Valid"

def prepare_item_data_for_db(name: str, category: str, subcategory: str, research_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare item data for database insertion"""
    item_data = {
        'name': name,
        'category': category,
        'subcategory': subcategory,
        'item_year': research_data.get('item_year'),
        'item_year_to': research_data.get('item_year_to'),
        'reference_url': research_data.get('reference_url'),
        'image_url': research_data.get('image_url'),
        'group': research_data.get('group'),
        'view_count': 0,
        'selection_count': 0
    }
    
    # Remove None values and empty strings
    return {k: v for k, v in item_data.items() if v is not None and v != ''}