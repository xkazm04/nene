import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from config.database_top import supabase
from supabase import Client
from models.top_models.item_group import (
    ItemGroupCreate, 
    ItemGroupUpdate, 
    ItemGroupResponse, 
    ItemGroupWithCount,
    ItemGroupWithItems,
    GroupItemResponse,
    ItemGroupSearchParams
)
from models.top_models.enums import CategoryEnum

logger = logging.getLogger(__name__)

class ItemGroupsService:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    async def get_groups_with_counts(self, params: ItemGroupSearchParams) -> List[ItemGroupWithCount]:
        """Get item groups with item counts using the database function"""
        try:
            # Convert enum to string for database
            category_str = params.category.value if params.category else None
            
            # Use Supabase RPC to call the database function
            result = self.supabase.rpc('get_groups_with_counts', {
                'p_category': category_str,
                'p_subcategory': params.subcategory,
                'p_search': params.search,
                'p_min_item_count': 1  # Add this parameter
            }).execute()
            
            if not result.data:
                logger.warning("RPC returned no data, falling back to direct query")
                return await self._get_groups_by_category_optimized(
                    category_str, params.subcategory, params.search, params.limit
                )
            
            groups = []
            for row in result.data:
                group = ItemGroupWithCount(
                    id=row['group_id'],
                    name=row['group_name'],
                    description=row['group_description'],
                    category=CategoryEnum(row['group_category']),
                    subcategory=row['group_subcategory'],
                    image_url=row['group_image_url'],
                    item_count=row['item_count'],
                    created_at=row['group_created_at'],
                    updated_at=row['group_updated_at']
                )
                groups.append(group)
            
            # Apply offset and limit
            start_idx = params.offset
            end_idx = start_idx + params.limit
            
            return groups[start_idx:end_idx]
            
        except Exception as e:
            logger.error(f"Error fetching groups with counts: {e}")
            # Fall back to optimized query
            category_str = params.category.value if params.category else None
            return await self._get_groups_by_category_optimized(
                category_str, params.subcategory, params.search, params.limit
            )

    async def get_group_by_id(self, group_id: uuid.UUID, include_items: bool = True) -> Optional[ItemGroupWithItems]:
        """Get a specific item group by ID with items included by default"""
        try:
            # Get group basic info
            result = self.supabase.table('item_groups').select(
                'id, name, category, subcategory, description, image_url, created_at, updated_at'
            ).eq('id', str(group_id)).execute()
            
            if not result.data:
                return None
                
            group_data = result.data[0]
            
            # Get items for this group if requested
            items = []
            if include_items:
                items_result = self.supabase.table('items').select('''
                    id,
                    name,
                    description,
                    category,
                    subcategory,
                    item_year,
                    item_year_to,
                    image_url,
                    created_at
                ''').eq('group_id', str(group_id)).order('name').execute()
                
                if items_result.data:
                    items = [
                        GroupItemResponse(
                            id=item['id'],
                            name=item['name'],
                            description=item['description'],
                            category=item['category'],
                            subcategory=item['subcategory'],
                            item_year=item['item_year'],
                            item_year_to=item['item_year_to'],
                            image_url=item['image_url'],
                            created_at=item['created_at']
                        )
                        for item in items_result.data
                    ]
            
            return ItemGroupWithItems(
                id=group_data['id'],
                name=group_data['name'],
                description=group_data['description'],
                category=CategoryEnum(group_data['category']),
                subcategory=group_data['subcategory'],
                image_url=group_data['image_url'],
                item_count=len(items),
                items=items,
                created_at=group_data['created_at'],
                updated_at=group_data['updated_at']
            )
            
        except Exception as e:
            logger.error(f"Error fetching group {group_id}: {e}")
            raise

    async def get_groups_by_category(
        self,
        category: str,
        subcategory: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        min_item_count: int = 1
    ) -> List[ItemGroupWithCount]:
        """OPTIMIZED: Get groups filtered by category with item counts in a single query"""
        try:
            # Use a single efficient query instead of individual lookups
            base_query = self.supabase.table('item_groups').select('''
                id,
                name,
                description,
                category,
                subcategory,
                image_url,
                created_at,
                updated_at,
                items!inner(id)
            ''', count='exact')
            
            # Apply filters
            query = base_query.eq('category', category)
            
            if subcategory:
                query = query.eq('subcategory', subcategory)
            
            if search:
                query = query.ilike('name', f'%{search}%')
            
            # Execute with items join to get counts
            result = query.order('name').limit(limit).execute()
            
            if not result.data:
                logger.info(f"No groups found for category {category}")
                return []
            
            # Process results and calculate item counts
            groups = []
            for row in result.data:
                # Count items for this group efficiently
                item_count = len(row.get('items', []))
                
                # Skip if below minimum count
                if item_count < min_item_count:
                    continue
                
                # Remove items data to clean up response
                clean_row = {k: v for k, v in row.items() if k != 'items'}
                
                group = ItemGroupWithCount(
                    id=clean_row['id'],
                    name=clean_row['name'],
                    description=clean_row['description'],
                    category=CategoryEnum(clean_row['category']),
                    subcategory=clean_row['subcategory'],
                    image_url=clean_row['image_url'],
                    item_count=item_count,
                    created_at=clean_row['created_at'],
                    updated_at=clean_row['updated_at']
                )
                groups.append(group)
            
            logger.info(f"Found {len(groups)} groups for category {category} with min_item_count={min_item_count}")
            return groups
            
        except Exception as e:
            logger.error(f"Error in optimized query for category {category}: {e}")
            # Last resort fallback
            return await self._get_groups_by_category_fallback(
                category, subcategory, search, limit, min_item_count
            )

    async def _get_groups_by_category_optimized(
        self,
        category: str,
        subcategory: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100
    ) -> List[ItemGroupWithCount]:
        """Optimized fallback using batch queries"""
        try:
            # Get groups first
            query_builder = self.supabase.table('item_groups').select('''
                id,
                name,
                description,
                category,
                subcategory,
                image_url,
                created_at,
                updated_at
            ''').eq('category', category)
            
            if subcategory:
                query_builder = query_builder.eq('subcategory', subcategory)
            
            if search:
                query_builder = query_builder.ilike('name', f'%{search}%')
            
            result = query_builder.order('name').limit(limit).execute()
            
            if not result.data:
                return []
            
            # Get item counts in batch using a single query with group by
            group_ids = [row['id'] for row in result.data]
            
            # Batch query for item counts
            counts_result = self.supabase.table('items').select(
                'group_id',
                count='exact'
            ).in_('group_id', group_ids).execute()
            
            # Create item count mapping (this might need adjustment based on Supabase response)
            item_counts = {}
            if counts_result.data:
                # This approach might need modification based on how Supabase handles group by
                for group_id in group_ids:
                    count_result = self.supabase.table('items').select('id', count='exact').eq('group_id', group_id).execute()
                    item_counts[group_id] = count_result.count if count_result.count is not None else 0
            
            # Build response
            groups = []
            for row in result.data:
                item_count = item_counts.get(row['id'], 0)
                
                # Skip empty groups
                if item_count == 0:
                    continue
                
                group = ItemGroupWithCount(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    category=CategoryEnum(row['category']),
                    subcategory=row['subcategory'],
                    image_url=row['image_url'],
                    item_count=item_count,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                groups.append(group)
            
            return groups
            
        except Exception as e:
            logger.error(f"Error in optimized fallback: {e}")
            return []

    async def create_group(self, group_data: ItemGroupCreate) -> ItemGroupResponse:
        """Create a new item group"""
        try:
            result = self.supabase.table('item_groups').insert({
                'name': group_data.name,
                'category': group_data.category.value,
                'subcategory': group_data.subcategory,
                'description': group_data.description,
                'image_url': group_data.image_url
            }).execute()
            
            if not result.data:
                raise Exception("Failed to create group")
            
            row = result.data[0]
            return ItemGroupResponse(
                id=row['id'],
                name=row['name'],
                category=CategoryEnum(row['category']),
                subcategory=row['subcategory'],
                description=row['description'],
                image_url=row['image_url'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
        except Exception as e:
            logger.error(f"Error creating group: {e}")
            raise

    async def get_group_items(self, group_id: uuid.UUID, limit: int = 50, offset: int = 0) -> List[dict]:
        """Get all items belonging to a specific group - legacy endpoint"""
        try:
            result = self.supabase.table('items').select(
                'id, name, description, category, subcategory, item_year, item_year_to, image_url, created_at'
            ).eq('group_id', str(group_id)).order('name').range(offset, offset + limit - 1).execute()
            
            items = []
            for row in result.data if result.data else []:
                item = {
                    'id': str(row['id']),
                    'name': row['name'],
                    'description': row['description'],
                    'category': row['category'],
                    'subcategory': row['subcategory'],
                    'item_year': row['item_year'],
                    'item_year_to': row['item_year_to'],
                    'image_url': row['image_url'],
                    'created_at': row['created_at']
                }
                items.append(item)
            
            return items
            
        except Exception as e:
            logger.error(f"Error fetching items for group {group_id}: {e}")
            raise

    async def get_name_suggestions(
        self, 
        query: str, 
        category: Optional[CategoryEnum] = None,
        subcategory: Optional[str] = None,
        limit: int = 10
    ) -> List[str]:
        """Get group name suggestions for autocomplete"""
        try:
            query_builder = self.supabase.table('item_groups').select('name').ilike('name', f'%{query}%')
            
            if category:
                query_builder = query_builder.eq('category', category.value)
                if subcategory:
                    query_builder = query_builder.eq('subcategory', subcategory)
            
            result = query_builder.order('name').limit(limit).execute()
            
            return [row['name'] for row in result.data] if result.data else []
            
        except Exception as e:
            logger.error(f"Error getting name suggestions: {e}")
            raise

# Create service instance
item_groups_service = ItemGroupsService(supabase)