from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
from models.top_models.enums import CategoryEnum

class ItemGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Group name")
    category: CategoryEnum = Field(..., description="Category this group belongs to")
    subcategory: Optional[str] = Field(None, max_length=100, description="Subcategory if applicable")
    description: Optional[str] = Field(None, description="Group description")
    image_url: Optional[str] = Field(None, description="Group image URL")

class ItemGroupCreate(ItemGroupBase):
    pass

class ItemGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    image_url: Optional[str] = None

class ItemGroupResponse(ItemGroupBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ItemGroupWithCount(ItemGroupResponse):
    item_count: int = Field(..., description="Number of items in this group")

class GroupItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    item_year: Optional[int] = None
    item_year_to: Optional[int] = None
    image_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ItemGroupWithItems(ItemGroupResponse):
    item_count: int = Field(..., description="Number of items in this group")
    items: List[GroupItemResponse] = Field(default_factory=list, description="Items in this group")

class ItemGroupSearchParams(BaseModel):
    category: Optional[CategoryEnum] = None
    subcategory: Optional[str] = None
    search: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
    include_items: bool = Field(False, description="Whether to include items in the response")
    items_limit: int = Field(20, ge=1, le=100, description="Max items per group when include_items=True")