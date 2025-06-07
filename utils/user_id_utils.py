import uuid
import re
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class UserIdInfo:
    def __init__(self, user_id: str, is_temporary: bool, is_valid: bool):
        self.user_id = user_id
        self.is_temporary = is_temporary
        self.is_valid = is_valid

def is_valid_uuid(user_id: str) -> bool:
    """Check if string is a valid UUID format"""
    try:
        uuid.UUID(user_id)
        return True
    except (ValueError, TypeError):
        return False

def extract_user_id_info(user_id: str) -> UserIdInfo:
    """Extract and validate user ID information"""
    if not user_id:
        return UserIdInfo("", False, False)
    
    # Handle temp_ prefixed IDs (legacy support)
    if user_id.startswith('temp_'):
        clean_id = user_id[5:]  # Remove 'temp_' prefix
        is_valid = is_valid_uuid(clean_id)
        return UserIdInfo(clean_id, True, is_valid)
    
    # Handle regular UUIDs
    is_valid = is_valid_uuid(user_id)
    return UserIdInfo(user_id, False, is_valid)

def sanitize_user_id_for_db(user_id: str) -> str:
    """Sanitize user ID for database operations"""
    info = extract_user_id_info(user_id)
    
    if not info.is_valid:
        raise ValueError(f"Invalid user ID format: {user_id}")
    
    return info.user_id

def create_temp_user_id() -> str:
    """Create a new temporary user ID (clean UUID)"""
    return str(uuid.uuid4())

def is_temporary_user(user_id: str) -> bool:
    """Check if user ID represents a temporary user"""
    info = extract_user_id_info(user_id)
    return info.is_temporary

def convert_to_uuid(user_id: str) -> uuid.UUID:
    """Convert string user ID to UUID object"""
    sanitized = sanitize_user_id_for_db(user_id)
    return uuid.UUID(sanitized)