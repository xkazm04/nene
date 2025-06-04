from typing import List, Optional, Dict, Any
import uuid
from supabase import Client
import logging
from models.top import (
    ListCreate, ListUpdate, ListResponse, ListWithItems,
    CategoryEnum,
    ListAnalyticsResponse, ListItemCreate,

)

logger = logging.getLogger(__name__)

class TopListsService:
    def __init__(self, supabase: Client):
        self.supabase = supabase
    async def create_list(self, list_data: ListCreate) -> ListResponse:
        """Create a new list"""
        try:
            result = self.supabase.table('lists').insert(list_data.dict()).execute()
            if result.data:
                return ListResponse(**result.data[0])
            raise Exception("Failed to create list")
        except Exception as e:
            logger.error(f"Error creating list: {e}")
            raise

    async def get_list_by_id(self, list_id: uuid.UUID, include_items: bool = False) -> Optional[ListWithItems]:
        """Get list by ID with optional items"""
        try:
            result = self.supabase.table('lists').select('*').eq('id', str(list_id)).execute()
            if not result.data:
                return None
            
            list_data = ListResponse(**result.data[0])
            
            if include_items:
                items = await self.get_list_items(list_id)
                return ListWithItems(**list_data.dict(), items=items, total_items=len(items))
            else:
                return ListWithItems(**list_data.dict(), items=[], total_items=0)
        except Exception as e:
            logger.error(f"Error getting list {list_id}: {e}")
            raise

    async def update_list(self, list_id: uuid.UUID, list_data: ListUpdate) -> Optional[ListResponse]:
        """Update a list"""
        try:
            update_data = {k: v for k, v in list_data.dict().items() if v is not None}
            result = self.supabase.table('lists').update(update_data).eq('id', str(list_id)).execute()
            if result.data:
                return ListResponse(**result.data[0])
            return None
        except Exception as e:
            logger.error(f"Error updating list {list_id}: {e}")
            raise

    async def delete_list(self, list_id: uuid.UUID) -> bool:
        """Delete a list"""
        try:
            result = self.supabase.table('lists').delete().eq('id', str(list_id)).execute()
            return len(result.data) > 0 if result.data else False
        except Exception as e:
            logger.error(f"Error deleting list {list_id}: {e}")
            raise

    async def search_lists(
        self,
        user_id: Optional[uuid.UUID] = None,
        category: Optional[CategoryEnum] = None,
        subcategory: Optional[str] = None,
        predefined: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ListResponse]:
        """Search lists with filters"""
        try:
            query = self.supabase.table('lists').select('*')
            
            if user_id:
                query = query.eq('user_id', str(user_id))
            if category:
                query = query.eq('category', category.value)
            if subcategory:
                query = query.eq('subcategory', subcategory)
            if predefined is not None:
                query = query.eq('predefined', predefined)
            
            result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            
            return [ListResponse(**list_item) for list_item in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error searching lists: {e}")
            raise
    # Add these methods to your existing TopListsService class

    async def get_list_analytics(self, list_id: uuid.UUID) -> Optional[ListAnalyticsResponse]:
        """Get comprehensive analytics for a list"""
        try:
            # Get vote statistics
            votes_result = self.supabase.table('user_votes').select('vote_value', count='exact').eq('list_id', str(list_id)).execute()
            total_votes = votes_result.count or 0
            
            # Get comment count
            comments_result = self.supabase.table('list_comments').select('id', count='exact').eq('list_id', str(list_id)).execute()
            total_comments = comments_result.count or 0
            
            # Get follower count
            followers_result = self.supabase.table('list_follows').select('user_id', count='exact').eq('list_id', str(list_id)).execute()
            follower_count = followers_result.count or 0
            
            # Calculate engagement rate
            list_items_count = self.supabase.table('list_items').select('id', count='exact').eq('list_id', str(list_id)).execute().count or 1
            engagement_rate = (total_votes + total_comments) / max(list_items_count, 1)
            
            # Get average ranking
            avg_ranking_result = self.supabase.table('list_items').select('ranking').eq('list_id', str(list_id)).execute()
            average_ranking = sum(item['ranking'] for item in avg_ranking_result.data) / len(avg_ranking_result.data) if avg_ranking_result.data else 0
            
            # Find most controversial item (most votes with mixed sentiment)
            controversial_item = await self._find_most_controversial_item(list_id)
            
            # Get version count
            versions_result = self.supabase.table('list_versions').select('id', count='exact').eq('list_id', str(list_id)).execute()
            version_count = versions_result.count or 0
            
            return ListAnalyticsResponse(
                list_id=list_id,
                total_votes=total_votes,
                total_comments=total_comments,
                follower_count=follower_count,
                engagement_rate=engagement_rate,
                average_item_ranking=average_ranking,
                most_controversial_item_id=controversial_item,
                version_count=version_count
            )
            
        except Exception as e:
            logger.error(f"Error getting list analytics: {e}")
            raise


    async def clone_list_with_modifications(self, source_list_id: uuid.UUID, user_id: uuid.UUID, modifications: Dict[str, Any]) -> ListResponse:
        """Clone a list with modifications"""
        try:
            # Get source list
            source_list = await self.get_list_by_id(source_list_id, include_items=True)
            if not source_list:
                raise Exception("Source list not found")
            
            # Create new list with modifications
            new_list_data = ListCreate(
                title=modifications.get('title', f"Copy of {source_list.title}"),
                category=modifications.get('category', source_list.category),
                subcategory=modifications.get('subcategory', source_list.subcategory),
                user_id=user_id,
                size=modifications.get('size', source_list.size),
                time_period=modifications.get('time_period', source_list.time_period),
                parent_list_id=source_list_id
            )
            
            # Create the new list
            new_list = await self.create_list(new_list_data, user_id)
            
            # Copy items if requested
            if modifications.get('copy_items', True):
                from .top_item import top_items_service
                for item in source_list.items:
                    list_item_data = ListItemCreate(
                        list_id=new_list.id,
                        item_id=item.item.id,
                        ranking=item.ranking
                    )
                    await top_items_service.add_item_to_list(list_item_data, user_id)
            
            return new_list
            
        except Exception as e:
            logger.error(f"Error cloning list: {e}")
            raise

    async def get_list_version_comparison(self, list_id: uuid.UUID, version1: int, version2: int) -> Dict[str, Any]:
        """Compare two versions of a list"""
        try:
            v1_result = self.supabase.table('list_versions').select('snapshot_data').eq('list_id', str(list_id)).eq('version_number', version1).execute()
            v2_result = self.supabase.table('list_versions').select('snapshot_data').eq('list_id', str(list_id)).eq('version_number', version2).execute()
            
            if not v1_result.data or not v2_result.data:
                raise Exception("Version not found")
            
            v1_data = v1_result.data[0]['snapshot_data']
            v2_data = v2_result.data[0]['snapshot_data']
            
            # Compare items and rankings
            v1_items = {item['item']['id']: item['ranking'] for item in v1_data.get('items', [])}
            v2_items = {item['item']['id']: item['ranking'] for item in v2_data.get('items', [])}
            
            added_items = set(v2_items.keys()) - set(v1_items.keys())
            removed_items = set(v1_items.keys()) - set(v2_items.keys())
            ranking_changes = {
                item_id: {'old_rank': v1_items[item_id], 'new_rank': v2_items[item_id]}
                for item_id in set(v1_items.keys()) & set(v2_items.keys())
                if v1_items[item_id] != v2_items[item_id]
            }
            
            return {
                'version_1': version1,
                'version_2': version2,
                'added_items': list(added_items),
                'removed_items': list(removed_items),
                'ranking_changes': ranking_changes,
                'total_changes': len(added_items) + len(removed_items) + len(ranking_changes)
            }
            
        except Exception as e:
            logger.error(f"Error comparing list versions: {e}")
            raise

    
from config.database_top import supabase
top_lists_service = TopListsService(supabase)