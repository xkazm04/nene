from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
import uuid
import logging

from models.top_models.enums import CategoryEnum
from models.top_models.item_group import (
    ItemGroupCreate, 
    ItemGroupUpdate, 
    ItemGroupResponse, 
    ItemGroupWithCount,
    ItemGroupWithItems,
    ItemGroupSearchParams
)
from services.top.item_groups_service import item_groups_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["top-groups"])

@router.get("/", response_model=List[ItemGroupWithCount])
async def get_item_groups(
    category: Optional[CategoryEnum] = Query(None, description="Filter by category"),
    subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
    search: Optional[str] = Query(None, description="Search in group names"),
    limit: int = Query(50, ge=1, le=200, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """Get item groups with filtering and search capabilities"""
    try:
        logger.info(f"Fetching item groups - category: {category}, subcategory: {subcategory}, search: {search}")
        
        search_params = ItemGroupSearchParams(
            category=category,
            subcategory=subcategory,
            search=search,
            limit=limit,
            offset=offset
        )
        
        groups = await item_groups_service.get_groups_with_counts(search_params)
        logger.info(f"Found {len(groups)} groups")
        return groups
        
    except Exception as e:
        logger.error(f"Failed to fetch item groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories/{category}", response_model=List[ItemGroupWithCount])
async def get_groups_by_category(
    category: CategoryEnum,
    subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
    search: Optional[str] = Query(None, description="Search in group names"),
    limit: int = Query(100, ge=1, le=200, description="Number of results to return"),
    min_item_count: int = Query(1, ge=0, description="Minimum number of items in group")
):
    """Get item groups for a specific category with minimum item count filtering"""
    try:
        logger.info(f"Fetching groups for category: {category}, subcategory: {subcategory}, min_item_count: {min_item_count}")
        
        groups = await item_groups_service.get_groups_by_category(
            category=category.value,
            subcategory=subcategory,
            search=search,
            limit=limit,
            min_item_count=min_item_count  
        )
        
        # Additional server-side filtering to ensure data quality (backup)
        filtered_groups = [
            group for group in groups 
            if group.item_count >= min_item_count and group.category == category.value
        ]
        
        logger.info(f"Found {len(filtered_groups)} groups for category {category} (filtered from {len(groups)})")
        return filtered_groups
        
    except Exception as e:
        logger.error(f"Failed to fetch groups for category {category}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{group_id}", response_model=ItemGroupWithItems)
async def get_item_group(
    group_id: uuid.UUID,
    include_items: bool = Query(True, description="Whether to include items in the response")
):
    """Get a specific item group by ID with items included by default"""
    try:
        logger.info(f"Fetching group {group_id} with include_items={include_items}")
        
        group = await item_groups_service.get_group_by_id(group_id, include_items=include_items)
        if not group:
            raise HTTPException(status_code=404, detail="Item group not found")
        
        logger.info(f"Found group {group_id} with {len(group.items)} items")
        return group
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get item group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=ItemGroupResponse)
async def create_item_group(group_data: ItemGroupCreate):
    """Create a new item group"""
    try:
        logger.info(f"Creating item group: {group_data.name} in {group_data.category}")
        
        group = await item_groups_service.create_group(group_data)
        logger.info(f"Successfully created group: {group.id}")
        
        return group
        
    except ValueError as e:
        logger.error(f"Validation error creating group: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create item group: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{group_id}/items")
async def get_group_items(
    group_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Get all items belonging to a specific group - legacy endpoint for backward compatibility"""
    try:
        logger.info(f"Fetching items for group {group_id} (legacy endpoint)")
        
        items = await item_groups_service.get_group_items(group_id, limit, offset)
        return {
            "group_id": group_id,
            "items": items,
            "count": len(items)
        }
        
    except Exception as e:
        logger.error(f"Failed to get items for group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/suggestions")
async def get_group_name_suggestions(
    query: str = Query(..., min_length=1, description="Search query for group name suggestions"),
    category: Optional[CategoryEnum] = Query(None, description="Filter by category"),
    subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
    limit: int = Query(10, ge=1, le=50, description="Number of suggestions to return")
):
    """Get group name suggestions for autocomplete"""
    try:
        suggestions = await item_groups_service.get_name_suggestions(
            query=query,
            category=category,
            subcategory=subcategory,
            limit=limit
        )
        
        return {
            "query": query,
            "suggestions": suggestions
        }
        
    except Exception as e:
        logger.error(f"Failed to get group name suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))