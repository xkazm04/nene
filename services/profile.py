import os
import re
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class ProfileCreate(BaseModel):
    name: str
    avatar_url: Optional[str] = None
    country: Optional[str] = None  # ISO 3166-1 alpha-2 code
    party: Optional[str] = None

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    country: Optional[str] = None
    party: Optional[str] = None

class ProfileResponse(BaseModel):
    id: str
    name: str
    name_normalized: str
    avatar_url: Optional[str] = None
    country: Optional[str] = None
    party: Optional[str] = None
    created_at: str
    updated_at: str

class ProfileService:
    def __init__(self):
        """Initialize Supabase client with credentials from environment."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")
        
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Profile service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            raise

    def normalize_name(self, name: str) -> str:
        """
        Normalize name for consistent matching.
        
        Args:
            name: Original name string
            
        Returns:
            str: Normalized name for database storage and matching
        """
        if not name:
            return ""
        
        # Remove extra whitespace and convert to lowercase
        normalized = re.sub(r'\s+', ' ', name.strip()).lower()
        
        # Remove special characters except spaces, hyphens, and apostrophes
        normalized = re.sub(r"[^\w\s\-']", '', normalized)
        
        return normalized

    def get_or_create_profile(self, name: str) -> Optional[str]:
        """
        Get existing profile or create new one if name doesn't exist.
        
        Args:
            name: Person's name
            
        Returns:
            str: Profile ID if successful, None if failed
        """
        try:
            if not name or not name.strip():
                logger.warning("Empty name provided to get_or_create_profile")
                return None
            
            # Normalize the name for consistent matching
            normalized_name = self.normalize_name(name)
            
            if not normalized_name:
                logger.warning(f"Name normalization resulted in empty string: '{name}'")
                return None
            
            logger.debug(f"Looking for profile with normalized name: '{normalized_name}'")
            
            # Check if profile already exists
            response = self.supabase.table("profiles").select("id, name").eq("name_normalized", normalized_name).limit(1).execute()
            
            if response.data:
                existing_profile = response.data[0]
                logger.debug(f"Found existing profile: ID={existing_profile['id']}, Name='{existing_profile['name']}'")
                return existing_profile["id"]
            
            # Create new profile if doesn't exist
            logger.info(f"Creating new profile for: '{name}' (normalized: '{normalized_name}')")
            
            profile_data = {
                "name": name.strip(),
                "name_normalized": normalized_name
            }
            
            create_response = self.supabase.table("profiles").insert(profile_data).execute()
            
            if create_response.data:
                new_profile_id = create_response.data[0]["id"]
                logger.info(f"Successfully created new profile: ID={new_profile_id}, Name='{name}'")
                return new_profile_id
            else:
                logger.error(f"Failed to create profile - no data returned: '{name}'")
                return None
                
        except Exception as e:
            logger.error(f"Error in get_or_create_profile for name '{name}': {str(e)}")
            return None

    def get_profile_by_id(self, profile_id: str) -> Optional[ProfileResponse]:
        """
        Get profile by ID.
        
        Args:
            profile_id: Profile UUID
            
        Returns:
            ProfileResponse: Profile data if found, None otherwise
        """
        try:
            logger.debug(f"Retrieving profile: {profile_id}")
            
            response = self.supabase.table("profiles").select("*").eq("id", profile_id).limit(1).execute()
            
            if not response.data:
                logger.warning(f"Profile not found: {profile_id}")
                return None
            
            profile_data = response.data[0]
            return ProfileResponse(**profile_data)
            
        except Exception as e:
            logger.error(f"Failed to retrieve profile {profile_id}: {str(e)}")
            return None

    def update_profile(self, profile_id: str, updates: ProfileUpdate) -> Optional[ProfileResponse]:
        """
        Update profile by ID.
        
        Args:
            profile_id: Profile UUID
            updates: Fields to update
            
        Returns:
            ProfileResponse: Updated profile data if successful, None otherwise
        """
        try:
            logger.info(f"Updating profile: {profile_id}")
            
            # Prepare update data
            update_data = {}
            
            if updates.name is not None:
                update_data["name"] = updates.name.strip()
                update_data["name_normalized"] = self.normalize_name(updates.name)
            
            if updates.avatar_url is not None:
                update_data["avatar_url"] = updates.avatar_url
                
            if updates.country is not None:
                # Validate country code format (2 letters)
                if updates.country and len(updates.country) == 2:
                    update_data["country"] = updates.country.upper()
                elif updates.country == "":
                    update_data["country"] = None
                else:
                    logger.warning(f"Invalid country code format: {updates.country}")
                    
            if updates.party is not None:
                update_data["party"] = updates.party.strip() if updates.party else None
            
            if not update_data:
                logger.warning(f"No valid updates provided for profile: {profile_id}")
                return None
            
            response = self.supabase.table("profiles").update(update_data).eq("id", profile_id).execute()
            
            if response.data:
                updated_profile = response.data[0]
                logger.info(f"Successfully updated profile: {profile_id}")
                return ProfileResponse(**updated_profile)
            else:
                logger.error(f"Failed to update profile - no data returned: {profile_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to update profile {profile_id}: {str(e)}")
            return None

    def delete_profile(self, profile_id: str) -> bool:
        """
        Delete profile by ID.
        
        Args:
            profile_id: Profile UUID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Deleting profile: {profile_id}")
            
            response = self.supabase.table("profiles").delete().eq("id", profile_id).execute()
            
            if response.data:
                logger.info(f"Successfully deleted profile: {profile_id}")
                return True
            else:
                logger.warning(f"Profile not found for deletion: {profile_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete profile {profile_id}: {str(e)}")
            return False

    def search_profiles(
        self,
        search_text: Optional[str] = None,
        country: Optional[str] = None,
        party: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ProfileResponse]:
        """
        Search profiles with optional filters.
        
        Args:
            search_text: Text to search in names
            country: Filter by country code
            party: Filter by party
            limit: Maximum results to return
            offset: Number of results to skip
            
        Returns:
            List of profiles
        """
        try:
            logger.debug(f"Searching profiles: text='{search_text}', country='{country}', party='{party}'")
            
            query = self.supabase.table("profiles").select("*")
            
            if search_text:
                # Search in both original name and normalized name
                query = query.or_(f"name.ilike.%{search_text}%,name_normalized.ilike.%{search_text}%")
            
            if country:
                query = query.eq("country", country.upper())
                
            if party:
                query = query.ilike("party", f"%{party}%")
            
            response = query.order("name").range(offset, offset + limit - 1).execute()
            
            profiles = [ProfileResponse(**profile) for profile in response.data] if response.data else []
            
            logger.debug(f"Found {len(profiles)} profiles")
            return profiles
            
        except Exception as e:
            logger.error(f"Failed to search profiles: {str(e)}")
            return []

# Create service instance
profile_service = ProfileService()