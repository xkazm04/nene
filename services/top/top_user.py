from typing import Optional
import uuid
from supabase import Client
import logging
from models.top_models.user import UserCreate, UserResponse
from utils.user_id_utils import (
    sanitize_user_id_for_db, 
)

logger = logging.getLogger(__name__)

class TopUserService:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    # User CRUD operations
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user (temporary or permanent)"""
        try:
            # Generate ID if not provided
            user_dict = user_data.dict()
            if 'id' not in user_dict or not user_dict['id']:
                user_dict['id'] = str(uuid.uuid4())
            
            result = self.supabase.table('users').insert(user_dict).execute()
            if result.data:
                return UserResponse(**result.data[0])
            raise Exception("Failed to create user")
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def create_temporary_user(self) -> UserResponse:
        """Create a new temporary user with clean UUID"""
        try:
            temp_user_data = UserCreate(
                is_temporary=True,
                display_name="Guest User"
            )
            return await self.create_user(temp_user_data)
        except Exception as e:
            logger.error(f"Error creating temporary user: {e}")
            raise

    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:  # Changed from uuid.UUID to str
        """Get user by ID with flexible ID format handling"""
        try:
            # Handle both temp and regular user IDs
            sanitized_user_id = sanitize_user_id_for_db(user_id)
            
            result = self.supabase.table('users').select('*').eq('id', sanitized_user_id).execute()
            if result.data:
                return UserResponse(**result.data[0])
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise

    async def convert_temporary_to_permanent(
        self, 
        temp_user_id: str, 
        username: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> UserResponse:
        """Convert a temporary user to a permanent user"""
        try:
            sanitized_user_id = sanitize_user_id_for_db(temp_user_id)
            
            # Verify temp user exists
            user = await self.get_user_by_id(sanitized_user_id)
            
            # Update user to permanent
            update_data = {
                'username': username,
                'display_name': display_name or user.display_name
            }
            
            result = self.supabase.table('users').update(update_data).eq('id', sanitized_user_id).execute()
            
            if result.data:
                return UserResponse(**result.data[0])
            raise Exception("Failed to convert temporary user")
            
        except Exception as e:
            logger.error(f"Error converting temporary user {temp_user_id}: {e}")
            raise

# Initialize service instance
from config.database_top import supabase
top_user_service = TopUserService(supabase)