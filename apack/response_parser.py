import json
import logging
from typing import List, Dict, Union

logger = logging.getLogger(__name__)


def parse_llm_response(response: Union[str, Dict, List], num_items: int) -> List[Dict]:
    """
    Parse the LLM response and extract valid JSON.
    
    Args:
        response: Raw LLM response (string, dict, or list)
        num_items: Maximum number of items to return
    
    Returns:
        List of validated dictionary items
    """
    
    try:
        # Handle different response types
        if isinstance(response, list):
            # Response is already a list
            result = response
        elif isinstance(response, dict):
            # Response is a single dictionary - wrap in list
            result = [response]
        else:
            # Response is a string - parse JSON
            response_str = str(response).strip()
            
            # Remove any markdown formatting
            if response_str.startswith('```'):
                lines = response_str.split('\n')
                # Remove first and last lines if they're markdown markers
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                response_str = '\n'.join(lines)
            
            # First try to parse the entire string as JSON
            try:
                parsed = json.loads(response_str)
                if isinstance(parsed, list):
                    result = parsed
                elif isinstance(parsed, dict):
                    result = [parsed]
                else:
                    raise ValueError("Parsed JSON is not a dict or list")
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from text
                result = extract_json_from_text(response_str)
                if not result:
                    logger.error(f"Could not parse response as JSON: {response_str[:200]}...")
                    return []
        
        # Validate the result is a list
        if not isinstance(result, list):
            logger.error(f"Response is not a list: {type(result)}")
            return []
        
        # Validate and filter items
        valid_items = []
        for item in result[:num_items]:
            if validate_item(item):
                # Ensure item is a proper dict and make a copy to avoid reference issues
                valid_items.append(dict(item))
            else:
                logger.warning(f"Invalid item filtered out: {item}")
        
        return valid_items
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing response: {e}")
        return []


def validate_item(item: Dict) -> bool:
    """
    Validate that an item has required fields.
    
    Args:
        item: Dictionary item to validate
    
    Returns:
        True if item is valid, False otherwise
    """
    
    if not isinstance(item, dict):
        logger.warning(f"Item is not a dictionary: {type(item)}")
        return False
    
    # Check if it's an AgentAnalysis-like structure
    analysis_fields = ['agent_name', 'verdict', 'analysis']
    if all(field in item for field in analysis_fields):
        return True
    
    # Check if it's a research result structure
    research_fields = ['title', 'content']
    if all(field in item for field in research_fields):
        return True
    
    # Basic required fields that should be present in most responses
    basic_fields = ['title', 'creator']
    if all(field in item for field in basic_fields):
        return True
    
    # If it's a dictionary with any content, consider it valid
    # (This is more permissive for different response formats)
    if len(item) > 0:
        return True
    
    logger.warning(f"Item missing required fields: {item}")
    return False


def extract_json_from_text(text: str) -> List[Dict]:
    """
    Extract JSON arrays from text that might contain additional content.
    
    Args:
        text: Text that may contain JSON
    
    Returns:
        List of extracted JSON objects
    """
    
    import re
    
    # Multiple patterns to find JSON objects (single objects are more common in agent responses)
    patterns = [
        r'```json\s*(\{[\s\S]*?\})\s*```',  # Markdown code blocks with json
        r'```\s*(\{[\s\S]*?\})\s*```',     # Generic code blocks
        r'\{[\s\S]*?\}',                    # Basic object pattern
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        for match in matches:
            try:
                if isinstance(match, tuple):
                    match = match[0]  # Extract from regex group
                result = json.loads(match)
                if isinstance(result, dict):
                    return [result]  # Wrap single dict in list
                elif isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                continue
    
    # Try to find JSON arrays if single objects fail
    array_patterns = [
        r'```json\s*(\[[\s\S]*?\])\s*```',  # Markdown code blocks with json
        r'```\s*(\[[\s\S]*?\])\s*```',     # Generic code blocks
        r'\[[\s\S]*?\]',                    # Basic array pattern (last resort)
    ]
    
    for pattern in array_patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        for match in matches:
            try:
                if isinstance(match, tuple):
                    match = match[0]
                result = json.loads(match)
                if isinstance(result, list):
                    return result
                elif isinstance(result, dict):
                    return [result]  # Wrap in list
            except json.JSONDecodeError:
                continue
    
    return []