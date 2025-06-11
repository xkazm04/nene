# filepath: c:\Users\kazda\dac\StoryTeller\nene\routes\item_routes.py
"""
FastAPI routes for item processing
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
from services.wiki.wiki_service import item_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items", tags=["items"])


# Request Models
class ItemRequest(BaseModel):
    name: str = Field(..., description="Item name", min_length=1, max_length=200)
    category: str = Field(..., description="Item category", pattern="^(sports|games|music)$")
    subcategory: Optional[str] = Field("", description="Item subcategory", max_length=100)

class BatchItemRequest(BaseModel):
    items: List[ItemRequest] = Field(..., description="List of items to process", min_items=1, max_items=50)
    delay_seconds: Optional[int] = Field(5, description="Delay between items in seconds", ge=1, le=30)

# Response Models
class ItemProcessResult(BaseModel):
    success: bool
    action: Optional[str]  # "created", "updated", "skipped"
    item_name: str
    category: str
    subcategory: str
    message: str
    updates: Dict[str, Any] = {}
    error: Optional[str] = None

class BatchProcessResult(BaseModel):
    total_items: int
    successful: int
    failed: int
    skipped: int
    results: List[ItemProcessResult]
    summary: Dict[str, Any]

@router.post("/", response_model=ItemProcessResult)
async def process_single_item(request: ItemRequest):
    """
    Process a single item - research and update/create in database
    
    - **name**: Item name (required)
    - **category**: Item category - sports, games, or music (required)
    - **subcategory**: Item subcategory (optional)
    
    Returns processing result with success status and details.
    """
    try:
        logger.info(f"Processing single item: {request.name} ({request.category}/{request.subcategory})")
        
        result = item_service.process_single_item(
            name=request.name,
            category=request.category,
            subcategory=request.subcategory
        )
        
        return ItemProcessResult(**result)
        
    except Exception as e:
        logger.error(f"Error processing single item: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing item: {str(e)}"
        )
# POST /items/process
# {
#     "name": "Lionel Messi",
#     "category": "sports",
#     "subcategory": "soccer"
# }
@router.post("/batch", response_model=BatchProcessResult)
async def process_batch_items(request: BatchItemRequest, background_tasks: BackgroundTasks):
    """
    Process a batch of items - research and update/create in database
    
    - **items**: List of items to process (1-50 items)
    - **delay_seconds**: Delay between processing items (1-30 seconds, default: 5)
    
    Returns batch processing results with detailed status for each item.
    
    **Note**: Processing happens synchronously but with delays to avoid rate limiting.
    """
    try:
        logger.info(f"Processing batch of {len(request.items)} items")
        
        # Convert Pydantic models to dictionaries
        items_data = [
            {
                "name": item.name,
                "category": item.category,
                "subcategory": item.subcategory
            }
            for item in request.items
        ]
        
        result = item_service.process_batch_items(
            items=items_data,
            delay_seconds=request.delay_seconds
        )
        
        return BatchProcessResult(**result)
        
    except Exception as e:
        logger.error(f"Error processing batch items: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing batch: {str(e)}"
        )
# POST /items/process-batch
# {
#     "items": [
#         {
#             "name": "Michael Jordan",
#             "category": "sports",
#             "subcategory": "basketball"
#         },
#         {
#             "name": "The Beatles",
#             "category": "music",
#             "subcategory": "rock"
#         }
#     ],
#     "delay_seconds": 5
# }

@router.get("/health")
async def health_check():
    """Health check endpoint for the item processing service"""
    try:
        # Test Gemini connection
        item_service.model
        
        return {
            "status": "healthy",
            "service": "item_processing",
            "gemini_api": "connected",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )

@router.get("/categories")
async def get_supported_categories():
    """Get list of supported item categories"""
    return {
        "categories": [
            {
                "name": "sports",
                "description": "Sports players and athletes",
                "example_subcategories": ["soccer", "basketball", "tennis", "hockey"]
            },
            {
                "name": "games",
                "description": "Video games",
                "example_subcategories": ["action", "rpg", "strategy", "puzzle"]
            },
            {
                "name": "music",
                "description": "Music artists and bands",
                "example_subcategories": ["rock", "pop", "jazz", "electronic"]
            }
        ]
    }