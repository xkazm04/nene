from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import uuid
import logging

from models.top import (ListWithItems)
from models.top_models.enums import CategoryEnum
from models.top_models.list import ListCreate, ListUpdate, ListAnalyticsResponse, ListCreationResponse, ListResponse
from services.top.top_lists import top_lists_service
from utils.user_id_utils import extract_user_id_info

logger = logging.getLogger(__name__)
router = APIRouter(tags=["top-lists"])

@router.post("/create-with-user", response_model=ListCreationResponse)
async def create_list_with_user(list_data: ListCreate):
    """Create a new list and automatically handle user creation if needed"""
    try:
        logger.info(f"=== CREATE LIST WITH USER ===")
        logger.info(f"Received data: {list_data.dict()}")
        
        # Create list with automatic user handling
        result = await top_lists_service.create_list_with_auto_user(list_data)
        
        logger.info(f"Successfully created list: {result['list'].id}")

        return ListCreationResponse(**result)
        
    except ValueError as e:
        logger.error(f"Validation error creating list: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create list with user: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e))

# Keep your other endpoints...
@router.post("/", response_model=ListResponse)
async def create_list(list_data: ListCreate):
    """Create a new list (legacy endpoint)"""
    try:
        logger.info(f"Creating list with legacy endpoint: {list_data.dict()}")
        return await top_lists_service.create_list(list_data)
    except ValueError as e:
        logger.error(f"Validation error creating list: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create list: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[ListResponse])
async def search_lists(
    user_id: Optional[str] = Query(None, description="Filter by user ID (supports temp_ prefix)"),
    category: Optional[CategoryEnum] = Query(None, description="Filter by category"),
    subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
    predefined: Optional[bool] = Query(None, description="Filter by predefined lists"),
    limit: int = Query(50, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """Search lists with filters and enhanced user ID handling"""
    try:
        return await top_lists_service.search_lists(
            user_id=user_id,
            category=category,
            subcategory=subcategory,
            predefined=predefined,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Failed to search lists: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{list_id}", response_model=ListWithItems)
async def get_list(
    list_id: str,
    include_items: bool = Query(True, description="Include list items in response")
):
    """Get a specific list by ID"""
    try:
        list_uuid = uuid.UUID(list_id)
        result = await top_lists_service.get_list_by_id(list_uuid, include_items)
        if not result:
            raise HTTPException(status_code=404, detail="List not found")
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid list ID format")
    except Exception as e:
        logger.error(f"Failed to get list {list_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{list_id}", response_model=ListResponse)
async def update_list(list_id: uuid.UUID, list_data: ListUpdate):
    """Update a list"""
    try:
        updated_list = await top_lists_service.update_list(list_id, list_data)
        if not updated_list:
            raise HTTPException(status_code=404, detail="List not found")
        return updated_list
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{list_id}")
async def delete_list(list_id: uuid.UUID):
    """Delete a list"""
    try:
        success = await top_lists_service.delete_list(list_id)
        if not success:
            raise HTTPException(status_code=404, detail="List not found")
        return {"message": "List deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete list: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# Add these routes to your existing top_lists.py

@router.get("/{list_id}/analytics", response_model=ListAnalyticsResponse)
async def get_list_analytics(list_id: uuid.UUID):
    """Get comprehensive analytics for a list"""
    try:
        analytics = await top_lists_service.get_list_analytics(list_id)
        if not analytics:
            raise HTTPException(status_code=404, detail="List analytics not found")
        return analytics
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get list analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{list_id}/clone")
async def clone_list(
    list_id: uuid.UUID, 
    clone_data: dict,
    user_id: uuid.UUID = Query(...)
):
    """Clone a list with modifications"""
    try:
        new_list = await top_lists_service.clone_list_with_modifications(list_id, user_id, clone_data)
        return {"message": "List cloned successfully", "new_list_id": new_list.id}
    except Exception as e:
        logger.error(f"Failed to clone list: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{list_id}/versions/compare")
async def compare_list_versions(
    list_id: uuid.UUID,
    version1: int = Query(..., description="First version to compare"),
    version2: int = Query(..., description="Second version to compare")
):
    """Compare two versions of a list"""
    try:
        comparison = await top_lists_service.get_list_version_comparison(list_id, version1, version2)
        return comparison
    except Exception as e:
        logger.error(f"Failed to compare versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

