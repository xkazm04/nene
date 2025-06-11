"""
Service for item research and database operations
"""
import google.generativeai as genai
import os
import time
import logging
from typing import Dict, Any, Optional, List
from config.database_top import supabase
from prompts.wiki_prompts import get_research_prompt
from services.wiki.wiki_utils import (
    extract_json_from_response,
    get_columns_to_update,
    validate_item_data,
    prepare_item_data_for_db
)

logger = logging.getLogger(__name__)

class ItemService:
    """Service for item research and database operations"""
    
    def __init__(self):
        self.setup_gemini()
        self.supabase = supabase
    
    def setup_gemini(self):
        """Initialize Gemini API"""
        try:
            api_key = os.environ['GOOGLE_API_KEY']
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-lite')
            logger.info("Gemini API configured successfully")
        except KeyError:
            logger.error("GOOGLE_API_KEY environment variable not set")
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        except Exception as e:
            logger.error(f"Could not configure Gemini API: {e}")
            raise
    
    def check_item_exists(self, name: str, category: str, subcategory: str) -> Optional[Dict[str, Any]]:
        """Check if item already exists in database"""
        try:
            response = self.supabase.table('items').select('*').eq('name', name).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Found existing item: {name}")
                return response.data[0]
            else:
                logger.info(f"Item not found in database: {name}")
                return None
                
        except Exception as e:
            logger.error(f"Error checking item existence: {e}")
            return None
    
    def get_research_data(self, name: str, category: str, subcategory: str, retry_count: int = 2) -> Optional[Dict[str, Any]]:
        """Get research data from Gemini API with retry logic"""
        for attempt in range(retry_count + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{retry_count}")
                    time.sleep(2)  # Wait 2 seconds between retries
                
                # Get the complete prompt
                prompt = get_research_prompt(name, category, subcategory)
                
                logger.info(f"Researching {name} ({category}/{subcategory})...")
                
                # Generate content
                response = self.model.generate_content(prompt)
                
                if response and response.text:
                    logger.info("Received response from Gemini")
                    
                    # Use improved JSON extraction
                    data = extract_json_from_response(response.text)
                    
                    if data:
                        if data.get('status') == 'failed':
                            logger.warning(f"Gemini couldn't find information for {name}")
                            if attempt < retry_count:
                                logger.info("Will retry with different approach...")
                                continue
                        return data
                    else:
                        logger.warning("Could not extract valid JSON from response")
                        if attempt < retry_count:
                            continue
                        logger.debug(f"Full response: {response.text}")
                        return None
                else:
                    logger.warning("Empty response from Gemini")
                    if attempt < retry_count:
                        continue
                    return None
                    
            except Exception as e:
                logger.error(f"Error getting research data (attempt {attempt + 1}): {e}")
                if attempt < retry_count:
                    continue
                return None
        
        return None
    
    def update_existing_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """Update existing item in database"""
        try:
            if not updates:
                logger.info("No updates needed for existing item")
                return True
            
            logger.info(f"Updating item {item_id} with: {updates}")
            
            response = self.supabase.table('items').update(updates).eq('id', item_id).execute()
            
            if response.data:
                logger.info(f"Successfully updated item with {len(updates)} fields")
                return True
            else:
                logger.error("Failed to update item - no data returned")
                return False
                
        except Exception as e:
            logger.error(f"Error updating item: {e}")
            return False
    
    def create_new_item(self, name: str, category: str, subcategory: str, research_data: Dict[str, Any]) -> bool:
        """Create new item in database"""
        try:
            # Prepare item data
            item_data = prepare_item_data_for_db(name, category, subcategory, research_data)
            
            logger.info(f"Creating new item: {item_data}")
            
            response = self.supabase.table('items').insert(item_data).execute()
            
            if response.data:
                logger.info(f"Successfully created new item: {name}")
                return True
            else:
                logger.error("Failed to create item - no data returned")
                return False
                
        except Exception as e:
            logger.error(f"Error creating item: {e}")
            return False
    
    def process_single_item(self, name: str, category: str, subcategory: str = '') -> Dict[str, Any]:
        """Process a single item - update or create"""
        result = {
            "success": False,
            "action": None,
            "item_name": name,
            "category": category,
            "subcategory": subcategory,
            "message": "",
            "updates": {},
            "error": None
        }
        
        try:
            logger.info(f"Processing: {name} ({category}/{subcategory})")
            
            # Step 1: Check if item exists
            existing_item = self.check_item_exists(name, category, subcategory)
            
            # Step 2: Get research data with retry
            research_data = self.get_research_data(name, category, subcategory, retry_count=2)
            
            if not research_data or research_data.get('status') == 'failed':
                result["message"] = f"No research data found for {name}"
                result["error"] = "research_failed"
                return result
            
            logger.info(f"Research data: {research_data}")
            
            # Step 3: Update or create
            if existing_item:
                # Update existing item
                updates = get_columns_to_update(existing_item, research_data)
                success = self.update_existing_item(existing_item['id'], updates)
                
                result["action"] = "updated"
                result["updates"] = updates
                result["success"] = success
                result["message"] = f"Updated existing item with {len(updates)} fields" if success else "Failed to update item"
                
            else:
                # Create new item
                success = self.create_new_item(name, category, subcategory, research_data)
                
                result["action"] = "created"
                result["success"] = success
                result["message"] = f"Created new item: {name}" if success else "Failed to create item"
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing item {name}: {e}")
            result["error"] = str(e)
            result["message"] = f"Error processing item: {str(e)}"
            return result
    
    def process_batch_items(self, items: List[Dict[str, str]], delay_seconds: int = 5) -> Dict[str, Any]:
        """Process a batch of items with improved error handling and delays"""
        batch_result = {
            "total_items": len(items),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "results": [],
            "summary": {}
        }
        
        logger.info(f"Starting batch processing of {len(items)} items...")
        
        for i, item in enumerate(items, 1):
            try:
                logger.info(f"[{i}/{len(items)}] Processing next item...")
                
                # Validate item data
                is_valid, validation_message = validate_item_data(item)
                if not is_valid:
                    logger.warning(f"Skipping invalid item: {item} - {validation_message}")
                    batch_result["skipped"] += 1
                    batch_result["results"].append({
                        "item": item,
                        "success": False,
                        "action": "skipped",
                        "message": validation_message,
                        "error": "validation_failed"
                    })
                    continue
                
                name = item['name'].strip()
                category = item['category'].strip()
                subcategory = item.get('subcategory', '').strip()
                
                logger.info(f"Item details: name='{name}', category='{category}', subcategory='{subcategory}'")
                
                # Process the item
                result = self.process_single_item(name, category, subcategory)
                batch_result["results"].append(result)
                
                if result["success"]:
                    batch_result["successful"] += 1
                else:
                    batch_result["failed"] += 1
                
                # Add delay between requests to avoid rate limiting
                if i < len(items):  # Don't wait after the last item
                    logger.info(f"Waiting {delay_seconds} seconds before next item...")
                    time.sleep(delay_seconds)
                    
            except Exception as e:
                logger.error(f"Error processing item {item}: {e}")
                batch_result["failed"] += 1
                batch_result["results"].append({
                    "item": item,
                    "success": False,
                    "action": "error",
                    "message": f"Processing error: {str(e)}",
                    "error": str(e)
                })
        
        # Create summary
        total_processed = batch_result["successful"] + batch_result["failed"]
        batch_result["summary"] = {
            "success_rate": (batch_result["successful"] / total_processed * 100) if total_processed > 0 else 0,
            "completion_status": "completed"
        }
        
        logger.info(f"Batch processing complete: {batch_result['successful']} successful, {batch_result['failed']} failed, {batch_result['skipped']} skipped")
        
        return batch_result

# Create service instance
item_service = ItemService()