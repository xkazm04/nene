from fastapi import APIRouter, HTTPException
import uuid
import logging

from models.top import (
    UserCreate, UserResponse,
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
async def get_user(user_id: uuid.UUID):
    """Get user by ID"""
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