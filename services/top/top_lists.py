from typing import List, Optional, Dict, Any
import uuid
from supabase import Client
import logging
from models.top import (
    ListResponse, ListWithItems,
    CategoryEnum, ListItemCreate
)
from models.top_models.list import ListCreate, ListUpdate, ListAnalyticsResponse
from models.top_models.user import UserResponse
from utils.user_id_utils import (
    extract_user_id_info, 
    sanitize_user_id_for_db,
)

logger = logging.getLogger(__name__)

class TopListsService:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    async def create_list_with_auto_user(self, list_data: ListCreate) -> Dict[str, Any]:
        """Create a list and automatically handle user creation if needed"""
        try:
            # Extract user ID info from the ORIGINAL user_id (before Pydantic cleaning)
            original_user_id = list_data.user_id  # This is already cleaned by Pydantic
            logger.info(f"Creating list with user_id: {original_user_id}")
            
            # Step 1: Ensure user exists (always create if not found)
            user_response = await self._ensure_user_exists(original_user_id)
            
            # Step 2: Create the list with the user ID
            list_response = await self._create_list_internal(list_data, str(user_response.id))
            
            # Step 3: Return combined response
            return {
                "list": list_response,
                "user": user_response,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error creating list with auto user: {e}")
            raise

    async def _ensure_user_exists(self, user_id: str) -> UserResponse:
        """Ensure user exists, create if not found - FIXED VERSION"""
        try:
            logger.info(f"Ensuring user exists: {user_id}")
            
            # First, try to find existing user
            result = self.supabase.table('users').select('*').eq('id', user_id).execute()
            
            if result.data:
                # User exists, return it
                logger.info(f"Found existing user: {user_id}")
                return UserResponse(**result.data[0])
            
            # User doesn't exist - CREATE TEMPORARY USER
            # For list creation flow, we ALWAYS create temporary users if they don't exist
            logger.info(f"User {user_id} not found, creating temporary user")
            
            temp_user_data = {
                'id': user_id,  # Use the provided UUID
                'display_name': 'Guest User',
                'username': None
            }
            
            result = self.supabase.table('users').insert(temp_user_data).execute()
            if result.data:
                logger.info(f"Successfully created temporary user: {user_id}")
                return UserResponse(**result.data[0])
            else:
                logger.error(f"Failed to insert temporary user: {user_id}")
                raise Exception("Failed to create temporary user")
                
        except Exception as e:
            logger.error(f"Error ensuring user exists for {user_id}: {e}")
            raise

    async def _create_list_internal(self, list_data: ListCreate, user_id: str) -> ListResponse:
        """Internal method to create list with verified user ID"""
        try:
            logger.info(f"Creating list internally for user: {user_id}")
            
            # Prepare data for database insertion
            db_data = list_data.dict()
            db_data['user_id'] = user_id
            # Remove fields that might not exist in the database schema
            db_data.pop('is_temporary_user', None)
            
            logger.info(f"Database data: {db_data}")
            
            # Insert into database
            result = self.supabase.table('lists').insert(db_data).execute()
            
            if result.data:
                response_data = result.data[0]
                logger.info(f"Successfully created list: {response_data.get('id')}")
                return ListResponse(**response_data)
            else:
                logger.error("No data returned from list insertion")
                raise Exception("Failed to create list - no data returned")
            
        except Exception as e:
            logger.error(f"Error creating list internally: {e}")
            raise

    async def create_list(self, list_data: ListCreate) -> ListResponse:
        """Legacy method - use create_list_with_auto_user for new implementations"""
        result = await self.create_list_with_auto_user(list_data)
        return result["list"]

    async def search_lists(
        self,
        user_id: Optional[str] = None,
        category: Optional[CategoryEnum] = None,
        subcategory: Optional[str] = None,
        predefined: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ListResponse]:
        """Search lists with enhanced user ID handling"""
        try:
            query = self.supabase.table('lists').select('*')
            
            if user_id:
                # Handle both temp and regular user IDs
                sanitized_user_id = sanitize_user_id_for_db(user_id)
                query = query.eq('user_id', sanitized_user_id)
                
            if category:
                query = query.eq('category', category.value)
            if subcategory:
                query = query.eq('subcategory', subcategory)
            if predefined is not None:
                query = query.eq('predefined', predefined)
            
            result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            
            lists = []
            for list_item in result.data if result.data else []:
                lists.append(ListResponse(**list_item))
                
            return lists
            
        except Exception as e:
            logger.error(f"Error searching lists: {e}")
            raise

    async def get_list_by_id(self, list_id: uuid.UUID, include_items: bool = False) -> Optional[ListWithItems]:
        """Get list by ID with optional items"""
        try:
            result = self.supabase.table('lists').select('*').eq('id', str(list_id)).execute()
            if not result.data:
                return None
            
            list_data = result.data[0]
            list_response = ListResponse(**list_data)
            
            if include_items:
                # You'll need to implement this method or mock it
                items = []  # await self.get_list_items(list_id)
                return ListWithItems(**list_response.dict(), items=items, total_items=len(items))
            else:
                return ListWithItems(**list_response.dict(), items=[], total_items=0)
                
        except Exception as e:
            logger.error(f"Error getting list {list_id}: {e}")
            raise

    async def update_list(self, list_id: uuid.UUID, list_data: ListUpdate) -> Optional[ListResponse]:
        """Update a list"""
        try:
            update_data = {k: v for k, v in list_data.dict().items() if v is not None}
            result = self.supabase.table('lists').update(update_data).eq('id', str(list_id)).execute()
            if result.data:
                response_data = result.data[0]
                return ListResponse(**response_data)
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

    async def get_list_analytics(self, list_id: uuid.UUID) -> Optional[ListAnalyticsResponse]:
        """Get comprehensive analytics for a list"""
        try:
            # Simplified version - implement based on your actual schema
            return ListAnalyticsResponse(
                list_id=list_id,
                total_votes=0,
                total_comments=0,
                follower_count=0,
                engagement_rate=0.0,
                average_item_ranking=0.0,
                most_controversial_item_id=None,
                version_count=1
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
                user_id=str(user_id),
                size=modifications.get('size', source_list.size),
                time_period=modifications.get('time_period', source_list.time_period),
                parent_list_id=source_list_id
            )
            
            # Create the new list
            new_list = await self.create_list(new_list_data)
            
            return new_list
            
        except Exception as e:
            logger.error(f"Error cloning list: {e}")
            raise

    async def get_list_version_comparison(self, list_id: uuid.UUID, version1: int, version2: int) -> Dict[str, Any]:
        """Compare two versions of a list"""
        try:
            # Simplified version - implement based on your actual schema
            return {
                'version_1': version1,
                'version_2': version2,
                'added_items': [],
                'removed_items': [],
                'ranking_changes': {},
                'total_changes': 0
            }
        except Exception as e:
            logger.error(f"Error comparing list versions: {e}")
            raise

# Initialize service instance
from config.database_top import supabase
top_lists_service = TopListsService(supabase)