import asyncio
import logging
import re
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from models.top_models.enums import CategoryEnum, ResearchDepth
from models.top import ItemCreate, ItemResponse
from services.llm_clients.groq_client import GroqLLMClient
from services.top.top_item import top_items_service
from config.database_top import supabase
from utils.metadata_prompt_builder import MetadataPromptBuilder
from prompts.wiki_prompts import get_research_prompt

logger = logging.getLogger(__name__)

class ItemMetadataService:
    """Service for researching item metadata using LLM + Simple Gemini research"""
    
    def __init__(self):
        self.llm_client = GroqLLMClient()
        self.prompt_builder = MetadataPromptBuilder()
        
        # Initialize Gemini for simple research (fallback)
        try:
            import google.generativeai as genai
            import os
            api_key = os.environ.get('GOOGLE_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
                self.gemini_available = True
                logger.info("Gemini model initialized for fallback research")
            else:
                self.gemini_available = False
                logger.warning("GOOGLE_API_KEY not found, Gemini fallback disabled")
        except Exception as e:
            self.gemini_available = False
            logger.warning(f"Failed to initialize Gemini: {e}")
        
        # Category-specific group mappings for validation
        self.category_group_mappings = {
            'games': {
                'video_games': [
                    'Action', 'Adventure', 'RPG', 'Strategy', 'Simulation', 
                    'Sports', 'Racing', 'Puzzle', 'Platform', 'Fighting',
                    'Shooter', 'Horror', 'Indie', 'MMO', 'MOBA'
                ]
            },
            'sports': {
                'soccer': ['Club Team', 'National Team', 'League'],
                'basketball': ['NBA Team', 'International Team', 'College'],
                'hockey': ['NHL Team', 'International Team', 'Junior League']
            },
            'music': {
                'artists': ['Pop', 'Rock', 'Hip-Hop', 'Electronic', 'Classical', 'Jazz', 'Country'],
                'albums': ['Studio Album', 'Live Album', 'Compilation', 'EP', 'Soundtrack']
            }
        }
    
    async def research_item_metadata(
        self, 
        name: str, 
        category: CategoryEnum, 
        subcategory: str, 
        user_description: Optional[str] = None,
        research_depth: ResearchDepth = ResearchDepth.standard
    ) -> Dict[str, Any]:
        """
        Research item metadata with LLM as primary source and Gemini for enhancement
        """
        try:
            logger.info(f"Researching metadata for: {name} ({category.value}/{subcategory}) - depth: {research_depth.value}")
            
            # Step 1: LLM Research (Primary) - Use LLM knowledge as the main source
            llm_result = await self._research_with_llm(name, category, subcategory, user_description)
            
            # Step 2: Gemini Research (Enhancement) - Only for missing attributes
            gemini_result = await self._research_with_gemini(name, category, subcategory, llm_result.get('llm_data', {}))
            
            # Step 3: Combine results with LLM as primary
            combined_result = self._combine_research_results(llm_result, gemini_result, category, subcategory)
            combined_result['research_depth'] = research_depth.value
            
            logger.info(f"Research completed for {name} with {combined_result['llm_confidence']}% confidence")
            return combined_result
            
        except Exception as e:
            logger.error(f"Item metadata research failed for {name}: {e}")
            return {
                'description': None,
                'group': None,
                'item_year': None,
                'item_year_to': None,
                'reference_url': None,
                'image_url': None,
                'llm_confidence': 0,
                'web_sources_found': 0,
                'research_method': 'failed',
                'research_errors': [str(e)],
                'research_depth': research_depth.value
            }
    
    async def _research_with_llm(
        self, 
        name: str, 
        category: CategoryEnum, 
        subcategory: str, 
        user_description: Optional[str]
    ) -> Dict[str, Any]:
        """Research using LLM (Groq) for metadata extraction - PRIMARY SOURCE"""
        try:
            if not self.llm_client.is_available():
                return {'llm_confidence': 0, 'llm_data': {}, 'llm_error': 'LLM client not available'}
            
            # Build specialized prompt for metadata research
            prompt = self.prompt_builder.build_metadata_prompt(name, category, subcategory, user_description)
            
            logger.info(f"Using LLM as primary metadata source for: {name}")
            
            # Use the specialized metadata research method
            metadata_response = self.llm_client.research_metadata(
                name=name,
                category=category.value,
                subcategory=subcategory,
                custom_prompt=prompt
            )
            
            # Validate and clean the metadata
            validated_metadata = self._validate_llm_metadata(metadata_response, category, subcategory)
            
            return {
                'llm_confidence': 90,  # High confidence for LLM training data
                'llm_data': validated_metadata,
                'llm_method': 'groq_metadata_research'
            }
            
        except Exception as e:
            logger.warning(f"LLM research failed for {name}: {e}")
            return {'llm_confidence': 0, 'llm_data': {}, 'llm_error': str(e)}
    
    async def _research_with_gemini(
        self, 
        name: str, 
        category: CategoryEnum, 
        subcategory: str,
        llm_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Research using Gemini for MISSING attributes only - Simple approach from new.py"""
        try:
            if not self.gemini_available:
                return {'gemini_confidence': 0, 'gemini_data': {}, 'gemini_error': 'Gemini not available'}
            
            # Check what's missing from LLM data
            missing_attributes = self._identify_missing_attributes(llm_data)
            
            if not missing_attributes:
                logger.info(f"All metadata available from LLM for {name}, skipping Gemini research")
                return {'gemini_confidence': 0, 'gemini_data': {}, 'gemini_info': 'No missing attributes'}
            
            logger.info(f"Using Gemini for missing attributes: {missing_attributes} for {name}")
            
            # Use the simple prompt approach from new.py
            prompt = get_research_prompt(name, category.value, subcategory)
            
            # Generate content with retry logic
            research_data = await self._get_gemini_research_with_retry(name, prompt, retry_count=2)
            
            if not research_data or research_data.get('status') == 'failed':
                return {
                    'gemini_confidence': 0, 
                    'gemini_data': {}, 
                    'gemini_error': 'Gemini research failed or no data found'
                }
            
            # Map research data to our format and filter for missing attributes only
            mapped_data = self._map_gemini_response(research_data, missing_attributes)
            
            return {
                'gemini_confidence': 75,
                'gemini_data': mapped_data,
                'gemini_method': 'simple_research',
                'missing_attributes_found': list(mapped_data.keys())
            }
            
        except Exception as e:
            logger.warning(f"Gemini research failed for {name}: {e}")
            return {'gemini_confidence': 0, 'gemini_data': {}, 'gemini_error': str(e)}
    
    async def _get_gemini_research_with_retry(self, name: str, prompt: str, retry_count: int = 2) -> Optional[Dict[str, Any]]:
        """Get research data from Gemini with retry logic - adapted from new.py"""
        for attempt in range(retry_count + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{retry_count} for {name}")
                    await asyncio.sleep(2)  # Wait between retries
                
                # Generate content
                response = self.gemini_model.generate_content(prompt)
                
                if response and response.text:
                    logger.info(f"Received response from Gemini for {name}")
                    
                    # Use improved JSON extraction from new.py
                    data = self._extract_json_from_response(response.text)
                    
                    if data:
                        if data.get('status') == 'failed':
                            logger.warning(f"Gemini couldn't find information for {name}")
                            if attempt < retry_count:
                                continue
                        return data
                    else:
                        logger.warning(f"Could not extract valid JSON from response for {name}")
                        if attempt < retry_count:
                            continue
                        return None
                else:
                    logger.warning(f"Empty response from Gemini for {name}")
                    if attempt < retry_count:
                        continue
                    return None
                    
            except Exception as e:
                logger.warning(f"Error getting Gemini research data (attempt {attempt + 1}) for {name}: {e}")
                if attempt < retry_count:
                    continue
                return None
        
        return None
    
    def _extract_json_from_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse JSON from Gemini response - adapted from new.py"""
        try:
            # Clean the response
            cleaned_text = self._clean_json_response(response_text)
            
            # Method 1: Try to parse the cleaned text directly
            try:
                data = json.loads(cleaned_text)
                return data
            except json.JSONDecodeError:
                pass
            
            # Method 2: Extract JSON blocks
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
                    json_block = re.sub(r',(\s*[}\]])', r'\1', json_block)
                    data = json.loads(json_block)
                    return data
                except json.JSONDecodeError:
                    continue
            
            # Method 3: Manual extraction
            return self._manual_json_extraction(cleaned_text)
            
        except Exception as e:
            logger.warning(f"Error in JSON extraction: {e}")
            return None
    
    def _clean_json_response(self, text: str) -> str:
        """Clean JSON response - from new.py"""
        # Remove markdown code block markers
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        text = text.strip()
        
        # Remove // comments from JSON
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            comment_match = re.search(r'(?<!:)//.*$', line)
            if comment_match:
                line = line[:comment_match.start()].rstrip()
                line = re.sub(r',\s*$', '', line)
            cleaned_lines.append(line)
        
        cleaned_text = '\n'.join(cleaned_lines)
        cleaned_text = re.sub(r',(\s*[}\]])', r'\1', cleaned_text)
        
        return cleaned_text.strip()
    
    def _manual_json_extraction(self, text: str) -> Optional[Dict[str, Any]]:
        """Manually extract data from JSON-like text - from new.py"""
        try:
            data = {}
            
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
                return data
            else:
                return None
                
        except Exception as e:
            logger.warning(f"Manual extraction error: {e}")
            return None
    
    def _map_gemini_response(self, research_data: Dict[str, Any], missing_attributes: List[str]) -> Dict[str, Any]:
        """Map Gemini research response to our metadata format"""
        mapped = {}
        
        # Map the fields we care about
        field_mappings = {
            'item_year': 'item_year',
            'item_year_to': 'item_year_to', 
            'reference_url': 'reference_url',
            'image_url': 'image_url',
            'group': 'group'
        }
        
        for research_field, metadata_field in field_mappings.items():
            if research_field in research_data and research_data[research_field] and metadata_field in missing_attributes:
                value = research_data[research_field]
                
                # Clean and validate the value
                if research_field in ['item_year', 'item_year_to']:
                    try:
                        # Convert string years to integers
                        year_value = int(str(value).strip('"'))
                        if 1800 <= year_value <= datetime.now().year + 2:
                            mapped[metadata_field] = year_value
                    except (ValueError, TypeError):
                        pass
                else:
                    # String fields
                    clean_value = str(value).strip('"')
                    if clean_value and clean_value != 'null':
                        mapped[metadata_field] = clean_value
        
        return mapped
    
    def _identify_missing_attributes(self, llm_data: Dict[str, Any]) -> List[str]:
        """Identify which attributes are missing from LLM data"""
        missing = []
        
        core_attributes = ['group', 'item_year']
        enhancement_attributes = ['reference_url', 'image_url', 'item_year_to']
        
        for attr in core_attributes:
            if not llm_data.get(attr):
                missing.append(attr)
        
        # Always try to get enhancement attributes
        missing.extend(enhancement_attributes)
        
        return missing
    
    def _validate_llm_metadata(self, raw_metadata: dict, category: CategoryEnum, subcategory: str) -> Dict[str, Any]:
        """Validate and clean LLM metadata response"""
        validated = {}
        
        try:
            # Description
            if 'description' in raw_metadata and raw_metadata['description']:
                validated['description'] = str(raw_metadata['description'])[:500]
            
            # Group with validation
            if 'group' in raw_metadata and raw_metadata['group']:
                group = str(raw_metadata['group'])
                validated['group'] = self._validate_group(group, category, subcategory)
            
            # Years
            if 'item_year' in raw_metadata and raw_metadata['item_year']:
                try:
                    year = int(raw_metadata['item_year'])
                    if 1800 <= year <= datetime.now().year + 2:
                        validated['item_year'] = year
                except (ValueError, TypeError):
                    pass
            
            if 'item_year_to' in raw_metadata and raw_metadata['item_year_to']:
                try:
                    year_to = int(raw_metadata['item_year_to'])
                    if 1800 <= year_to <= datetime.now().year + 2:
                        validated['item_year_to'] = year_to
                except (ValueError, TypeError):
                    pass
            
            return validated
            
        except Exception as e:
            logger.warning(f"Failed to validate LLM metadata: {e}")
            return {}
    
    def _validate_group(self, group: str, category: CategoryEnum, subcategory: str) -> str:
        """Validate and normalize group against known categories"""
        if category.value not in self.category_group_mappings:
            return group
        
        subcategory_groups = self.category_group_mappings[category.value].get(subcategory, [])
        
        # Try exact match
        for valid_group in subcategory_groups:
            if group.lower() == valid_group.lower():
                return valid_group
        
        # Try partial match
        for valid_group in subcategory_groups:
            if group.lower() in valid_group.lower() or valid_group.lower() in group.lower():
                return valid_group
        
        return group
    
    def _combine_research_results(
        self, 
        llm_result: Dict[str, Any], 
        gemini_result: Dict[str, Any], 
        category: CategoryEnum, 
        subcategory: str
    ) -> Dict[str, Any]:
        """Combine LLM and Gemini research results with LLM as primary source"""
        
        combined = {
            'description': None,
            'group': None,
            'item_year': None,
            'item_year_to': None,
            'reference_url': None,
            'image_url': None,
            'llm_confidence': 0,
            'web_sources_found': 0,
            'research_method': 'llm_primary_gemini_enhancement',
            'research_errors': []
        }
        
        # Collect errors
        if 'llm_error' in llm_result:
            combined['research_errors'].append(f"LLM: {llm_result['llm_error']}")
        if 'gemini_error' in gemini_result:
            combined['research_errors'].append(f"Gemini: {gemini_result['gemini_error']}")
        
        # Primary confidence is from LLM
        llm_confidence = llm_result.get('llm_confidence', 0)
        gemini_confidence = gemini_result.get('gemini_confidence', 0)
        
        # LLM is primary source, Gemini only adds to confidence if it fills gaps
        combined['llm_confidence'] = llm_confidence
        if gemini_confidence > 0 and gemini_result.get('gemini_data'):
            combined['llm_confidence'] = min(llm_confidence + 10, 95)  # Boost for Gemini enhancement
        
        combined['web_sources_found'] = 1 if gemini_confidence > 0 else 0
        
        # Combine data with LLM as primary
        llm_data = llm_result.get('llm_data', {})
        gemini_data = gemini_result.get('gemini_data', {})
        
        # Use LLM data first, fill gaps with Gemini data
        combined['description'] = llm_data.get('description') or gemini_data.get('description')
        combined['group'] = llm_data.get('group') or gemini_data.get('group')
        combined['item_year'] = llm_data.get('item_year') or gemini_data.get('item_year')
        combined['item_year_to'] = llm_data.get('item_year_to') or gemini_data.get('item_year_to')
        combined['reference_url'] = llm_data.get('reference_url') or gemini_data.get('reference_url')
        combined['image_url'] = llm_data.get('image_url') or gemini_data.get('image_url')
        
        # Add metadata about sources used
        combined['primary_source'] = 'groq_llm'
        combined['enhancement_source'] = 'gemini_research' if gemini_data else None
        combined['missing_attributes_filled'] = gemini_result.get('missing_attributes_found', [])
        
        return combined
    
    async def quick_validate_item(self, name: str, category: CategoryEnum, subcategory: str) -> int:
        """Quick validation to estimate research success confidence"""
        try:
            confidence = 50
            
            if len(name) > 2 and len(name) < 100:
                confidence += 10
            
            if self.llm_client.is_available():
                confidence += 30  # Higher weight for LLM availability
            
            if self.gemini_available:
                confidence += 15  # Weight for Gemini enhancement
            
            if category in [CategoryEnum.games, CategoryEnum.sports, CategoryEnum.music]:
                confidence += 10
            
            return min(confidence, 95)
            
        except Exception as e:
            logger.warning(f"Quick validation failed for {name}: {e}")
            return 20
    
    async def get_existing_groups(self, category: CategoryEnum) -> List[str]:
        """Get existing groups for a category from database"""
        try:
            result = supabase.table('items').select('group').eq('category', category.value).execute()
            
            groups = set()
            for item in result.data if result.data else []:
                if item.get('group'):
                    groups.add(item['group'])
            
            return sorted(list(groups))
            
        except Exception as e:
            logger.error(f"Failed to get existing groups for {category}: {e}")
            return []
    
    async def create_item_from_research(
        self, 
        name: str, 
        category: CategoryEnum, 
        subcategory: str, 
        research_data: Dict[str, Any]
    ) -> Optional[ItemResponse]:
        """Create item from research data"""
        try:
            item_create = ItemCreate(
                name=name,
                category=category,
                subcategory=subcategory,
                description=research_data.get('description', f"{subcategory.title()} item"),
                group=research_data.get('group'),
                item_year=research_data.get('item_year'),
                item_year_to=research_data.get('item_year_to'),
                image_url=research_data.get('image_url'),
                reference_url=research_data.get('reference_url')
            )
            
            created_item = await top_items_service.create_item(item_create)
            logger.info(f"Created item from research: {created_item.name} ({created_item.id})")
            
            return created_item
            
        except Exception as e:
            logger.error(f"Failed to create item from research: {e}")
            raise

# Create service instance
item_metadata_service = ItemMetadataService()