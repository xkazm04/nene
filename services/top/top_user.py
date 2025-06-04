from typing import Optional
import uuid
from supabase import Client
import logging
from models.top import (
    UserCreate, UserResponse,
)

logger = logging.getLogger(__name__)

class TopUserService:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    # User CRUD operations
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user"""
        try:
            result = self.supabase.table('users').insert(user_data.dict()).execute()
            if result.data:
                return UserResponse(**result.data[0])
            raise Exception("Failed to create user")
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[UserResponse]:
        """Get user by ID"""
        try:
            result = self.supabase.table('users').select('*').eq('id', str(user_id)).execute()
            if result.data:
                return UserResponse(**result.data[0])
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise

# Initialize service instance
from config.database_top import supabase
top_user_service = TopUserService(supabase)