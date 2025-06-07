from fastapi import APIRouter, HTTPException, Query
import logging

from models.top_models.user import (
    UserResponse, UserCreate
)
from services.top.top_user import top_user_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["top-users"])



# User routes
@router.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate):
    """Create a new user"""
    try:
        return await top_user_service.create_user(user)
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):  # Changed from uuid.UUID to str
    """Get user by ID (supports temp_ prefix)"""
    try:
        user = await top_user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/users/{user_id}/convert", response_model=UserResponse)
async def convert_temporary_user(
    user_id: str,
    email: str = Query(..., description="Email for permanent user"),
    username: str = Query(None, description="Username for permanent user"),
    display_name: str = Query(None, description="Display name for permanent user")
):
    """Convert temporary user to permanent user"""
    try:
        return await top_user_service.convert_temporary_to_permanent(
            user_id, email, username, display_name
        )
    except Exception as e:
        logger.error(f"Failed to convert temporary user: {e}")
        raise HTTPException(status_code=400, detail=str(e))