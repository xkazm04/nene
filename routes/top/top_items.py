from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import uuid
import logging

from models.top import (
    ItemCreate, ItemUpdate, ItemResponse, AccoladeCreate, AccoladeResponse,
    TagCreate, TagResponse, ItemStatisticsResponse, TrendingItemResponse,
    ListItemCreate, ListItemResponse, ListItemWithDetails,
    CategoryEnum, ImageUploadRequest, RerankRequest, ItemSearchFilters, BulkItemRequest,
    AdvancedItemSearchFilters, ItemAnalyticsResponse, ItemPopularityResponse,
    BulkAccoladeRequest, AccoladeType
)
from services.top.top_item import top_items_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["top-items"])

# Enhanced Item routes
@router.post("/items", response_model=ItemResponse)
async def create_item(item: ItemCreate, user_id: Optional[uuid.UUID] = None):
    """Create a new item with accolades and tags"""
    try:
        return await top_items_service.create_item(item)
    except Exception as e:
        logger.error(f"Failed to create item: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/items/bulk", response_model=List[ItemResponse])
async def create_items_bulk(bulk_request: BulkItemRequest):
    """Create multiple items at once"""
    try:
        results = []
        for item_data in bulk_request.items:
            try:
                result = await top_items_service.create_item(item_data)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to create item {item_data.name}: {e}")
                continue
        return results
    except Exception as e:
        logger.error(f"Failed to create items in bulk: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/items", response_model=List[ItemResponse])
async def search_items(
    category: Optional[CategoryEnum] = Query(None, description="Filter by category"),
    subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
    search: Optional[str] = Query(None, description="Search in item names and descriptions"),
    tags: List[str] = Query([], description="Filter by tags"),
    year_from: Optional[int] = Query(None, description="Filter from year"),
    year_to: Optional[int] = Query(None, description="Filter to year"),
    sort_by: str = Query("name", regex="^(name|popularity|recent|ranking)$", description="Sort order"),
    limit: int = Query(50, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """Enhanced search items with filters"""
    try:
        filters = ItemSearchFilters(
            category=category,
            subcategory=subcategory,
            search_query=search,
            tags=tags,
            year_from=year_from,
            year_to=year_to,
            sort_by=sort_by
        )
        return await top_items_service.search_items(filters, limit, offset)
    except Exception as e:
        logger.error(f"Failed to search items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/items/trending", response_model=List[TrendingItemResponse])
async def get_trending_items(
    category: Optional[CategoryEnum] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=50, description="Number of trending items to return")
):
    """Get trending items"""
    try:
        return await top_items_service.get_trending_items(category, limit)
    except Exception as e:
        logger.error(f"Failed to get trending items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: uuid.UUID, user_id: Optional[uuid.UUID] = Query(None)):
    """Get item by ID with view tracking"""
    try:
        item = await top_items_service.get_item_by_id(item_id, user_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get item: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/items/{item_id}/statistics", response_model=ItemStatisticsResponse)
async def get_item_statistics(item_id: uuid.UUID):
    """Get item performance statistics"""
    try:
        stats = await top_items_service.get_item_statistics(item_id)
        if not stats:
            raise HTTPException(status_code=404, detail="Item statistics not found")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get item statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/items/{item_id}", response_model=ItemResponse)
async def update_item(item_id: uuid.UUID, item_data: ItemUpdate):
    """Update an item"""
    try:
        item = await top_items_service.update_item(item_id, item_data)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update item: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/items/{item_id}/image", response_model=ItemResponse)
async def add_item_image(item_id: uuid.UUID, image_data: ImageUploadRequest):
    """Add image to an item"""
    try:
        item = await top_items_service.add_item_image(item_id, image_data.image_url)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add image to item: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Accolade routes
@router.post("/items/{item_id}/accolades", response_model=AccoladeResponse)
async def add_accolade(item_id: uuid.UUID, accolade_data: dict):
    """Add accolade to an item"""
    try:
        accolade = AccoladeCreate(item_id=item_id, **accolade_data)
        return await top_items_service.add_accolade(accolade)
    except Exception as e:
        logger.error(f"Failed to add accolade: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/items/{item_id}/accolades", response_model=List[AccoladeResponse])
async def get_item_accolades(item_id: uuid.UUID):
    """Get all accolades for an item"""
    try:
        return await top_items_service.get_item_accolades(item_id)
    except Exception as e:
        logger.error(f"Failed to get accolades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/accolades/{accolade_id}")
async def delete_accolade(accolade_id: uuid.UUID):
    """Delete an accolade"""
    try:
        success = await top_items_service.delete_accolade(accolade_id)
        if not success:
            raise HTTPException(status_code=404, detail="Accolade not found")
        return {"message": "Accolade deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete accolade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Tag routes
@router.post("/tags", response_model=TagResponse)
async def create_tag(tag: TagCreate):
    """Create a new tag"""
    try:
        return await top_items_service.create_tag(tag)
    except Exception as e:
        logger.error(f"Failed to create tag: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/tags", response_model=List[TagResponse])
async def get_all_tags():
    """Get all available tags"""
    try:
        return await top_items_service.get_all_tags()
    except Exception as e:
        logger.error(f"Failed to get tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/items/{item_id}/tags")
async def add_tags_to_item(item_id: uuid.UUID, tag_names: List[str]):
    """Add tags to an item"""
    try:
        success = await top_items_service.add_tags_to_item(item_id, tag_names)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add tags")
        return {"message": "Tags added successfully"}
    except Exception as e:
        logger.error(f"Failed to add tags to item: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Enhanced List Items routes
@router.post("/lists/{list_id}/items", response_model=ListItemResponse)
async def add_item_to_list(list_id: uuid.UUID, item_data: dict, user_id: Optional[uuid.UUID] = Query(None)):
    """Add item to list with selection tracking"""
    try:
        list_item_data = ListItemCreate(
            list_id=list_id,
            item_id=item_data['item_id'],
            ranking=item_data['ranking']
        )
        return await top_items_service.add_item_to_list(list_item_data, user_id)
    except Exception as e:
        logger.error(f"Failed to add item to list: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/lists/{list_id}/items", response_model=List[ListItemWithDetails])
async def get_list_items(list_id: uuid.UUID, user_id: Optional[uuid.UUID] = Query(None)):
    """Get all items in a list with vote information"""
    try:
        return await top_items_service.get_list_items(list_id, user_id)
    except Exception as e:
        logger.error(f"Failed to get list items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/lists/{list_id}/items/{item_id}")
async def remove_item_from_list(list_id: uuid.UUID, item_id: uuid.UUID):
    """Remove item from list"""
    try:
        success = await top_items_service.remove_item_from_list(list_id, item_id)
        if not success:
            raise HTTPException(status_code=404, detail="Item not found in list")
        return {"message": "Item removed from list successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove item from list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/lists/{list_id}/rerank", response_model=List[ListItemWithDetails])
async def rerank_list_items(list_id: uuid.UUID, rerank_data: RerankRequest, user_id: Optional[uuid.UUID] = Query(None)):
    """Rerank items in a list with versioning"""
    try:
        return await top_items_service.rerank_list_items(
            list_id, 
            rerank_data.item_rankings, 
            user_id,
            rerank_data.create_version,
            rerank_data.change_description
        )
    except Exception as e:
        logger.error(f"Failed to rerank list items: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
# Add these routes to your existing top_items.py

@router.get("/items/{item_id}/analytics", response_model=ItemAnalyticsResponse)
async def get_item_analytics(item_id: uuid.UUID):
    """Get comprehensive analytics for an item"""
    try:
        analytics = await top_items_service.get_item_analytics(item_id)
        if not analytics:
            raise HTTPException(status_code=404, detail="Item analytics not found")
        return analytics
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get item analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/items/search/advanced", response_model=List[ItemResponse])
async def advanced_search_items(
    category: Optional[CategoryEnum] = Query(None),
    subcategory: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    tags: List[str] = Query([]),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    min_popularity: Optional[int] = Query(None),
    has_accolades: Optional[bool] = Query(None),
    accolade_types: List[AccoladeType] = Query([]),
    min_appearances: Optional[int] = Query(None),
    ranking_position_filter: Optional[str] = Query(None, regex="^(top_10|top_3|first_place)$"),
    sort_by: str = Query("name", regex="^(name|popularity|recent|ranking)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Advanced search with analytics filters"""
    try:
        filters = AdvancedItemSearchFilters(
            category=category,
            subcategory=subcategory,
            search_query=search,
            tags=tags,
            year_from=year_from,
            year_to=year_to,
            min_popularity=min_popularity,
            has_accolades=has_accolades,
            accolade_types=accolade_types,
            min_appearances=min_appearances,
            ranking_position_filter=ranking_position_filter,
            sort_by=sort_by
        )
        return await top_items_service.search_items_advanced(filters, limit, offset)
    except Exception as e:
        logger.error(f"Failed advanced search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/accolades/bulk", response_model=List[AccoladeResponse])
async def create_bulk_accolades(bulk_request: BulkAccoladeRequest):
    """Create multiple accolades at once"""
    try:
        return await top_items_service.create_bulk_accolades(bulk_request.accolades)
    except Exception as e:
        logger.error(f"Failed to create bulk accolades: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/items/{item_id}/popularity", response_model=ItemPopularityResponse)
async def get_item_popularity_trends(item_id: uuid.UUID, days: int = Query(30, ge=1, le=365)):
    """Get item popularity trends"""
    try:
        return await top_items_service.get_item_popularity_trends(item_id, days)
    except Exception as e:
        logger.error(f"Failed to get popularity trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))