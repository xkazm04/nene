from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class UserCreate(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "username": "johndoe",
                "display_name": "John Doe"
            }
        }

class UserResponse(BaseModel):
    id: uuid.UUID
    username: Optional[str]
    display_name: Optional[str]
    created_at: datetime
    updated_at: datetime