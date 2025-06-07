from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid
from models.top_models.user import UserResponse
from utils.user_id_utils import extract_user_id_info

class CategoryEnum(str, Enum):
    sports = "sports"
    entertainment = "entertainment"
    games = "games"
    music = "music"
    other = "other"

class ListCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    category: CategoryEnum
    subcategory: Optional[str] = Field(None, max_length=100)
    user_id: str = Field(..., description="User ID (can be temporary with temp_ prefix or clean UUID)")
    predefined: bool = False
    size: int = Field(default=50, ge=1, le=1000)
    time_period: str = Field(default="all", max_length=50)
    parent_list_id: Optional[uuid.UUID] = None
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate and sanitize user ID - FIXED VERSION"""
        if not v:
            raise ValueError("User ID is required")
        
        try:
            user_info = extract_user_id_info(v)
            if not user_info.is_valid:
                raise ValueError(f"Invalid UUID format in user ID: {v}")
            
            # Return the clean UUID (without temp_ prefix)
            return user_info.user_id
            
        except Exception as e:
            try:
                uuid.UUID(v)
                return v
            except (ValueError, TypeError):
                raise ValueError(f"Invalid user ID format: {v}. Must be a valid UUID or temp_<UUID>")
    
    @validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "title": "Top 50 Basketball Players - All Time",
                "category": "sports",
                "subcategory": "basketball",
                "user_id": "temp_550e8400-e29b-41d4-a716-446655440000",
                "predefined": True,
                "size": 50,
                "time_period": "all"
            }
        }
        

        
class ListUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[CategoryEnum] = None
    subcategory: Optional[str] = Field(None, max_length=100)
    predefined: Optional[bool] = None
    size: Optional[int] = Field(None, ge=1, le=1000)
    time_period: Optional[str] = Field(None, max_length=50)
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError("Title cannot be empty")
        return v.strip() if v else v

class ListResponse(BaseModel):
    id: uuid.UUID
    title: str
    category: CategoryEnum
    subcategory: Optional[str]
    user_id: uuid.UUID  # Always returned as clean UUID
    predefined: bool
    size: int
    time_period: str
    parent_list_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    
class ListBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    category: CategoryEnum
    subcategory: Optional[str] = Field(None, max_length=100)
    user_id: Optional[uuid.UUID] = None
    predefined: bool = False
    size: int = Field(50, ge=1, le=100)
    time_period: str = Field("all", max_length=50)
    parent_list_id: Optional[uuid.UUID] = None
    
class ListVersionResponse(BaseModel):
    id: uuid.UUID
    list_id: uuid.UUID
    version_number: int
    snapshot_data: Dict[str, Any]
    change_description: Optional[str]
    created_by: Optional[uuid.UUID]
    created_at: datetime

    class Config:
        from_attributes = True
        
class ListCommentBase(BaseModel):
    comment_text: str = Field(..., min_length=1, max_length=2000)
    parent_comment_id: Optional[uuid.UUID] = None

class ListCommentCreate(ListCommentBase):
    list_id: uuid.UUID

class ListCommentResponse(ListCommentBase):
    id: uuid.UUID
    list_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    replies: List['ListCommentResponse'] = []

    class Config:
        from_attributes = True
        
class ListSearchFilters(BaseModel):
    user_id: Optional[uuid.UUID] = None
    category: Optional[CategoryEnum] = None
    subcategory: Optional[str] = None
    predefined: Optional[bool] = None
    has_items: Optional[bool] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    time_period: Optional[str] = None

class ListAnalyticsResponse(BaseModel):
    list_id: uuid.UUID
    total_votes: int
    total_comments: int
    follower_count: int
    engagement_rate: float
    average_item_ranking: float
    most_controversial_item_id: Optional[uuid.UUID]
    version_count: int

    class Config:
        from_attributes = True
        
class ListCreationResponse(BaseModel):
    """Combined response for list creation with user info"""
    list: ListResponse
    user: UserResponse
    success: bool
    
    class Config:
        schema_extra = {
            "example": {
                "list": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "title": "Top 50 Basketball Players - All Time",
                    "category": "sports",
                    "subcategory": "basketball",
                    "user_id": "550e8400-e29b-41d4-a716-446655440001",
                    "predefined": True,
                    "size": 50,
                    "time_period": "all",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z"
                },
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "display_name": "Guest User",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z"
                },
                "success": True
            }
        }



        
ListCommentResponse.model_rebuild()