from typing import Optional, List
from dotenv import load_dotenv
from supabase import create_client, Client
from pydantic import BaseModel, Field, validator
import logging
import os
import re

load_dotenv()

logger = logging.getLogger(__name__)

class ProfileCreate(BaseModel):
    name: str
    avatar_url: Optional[str] = None
    country: Optional[str] = None  # ISO 3166-1 alpha-2 code
    party: Optional[str] = None
    type: Optional[str] = Field(default="person", description="Type: person, media, organization, etc.")
    position: Optional[str] = Field(default=None, description="Position or role")
    bg_url: Optional[str] = Field(default=None, description="Background image URL")
    score: Optional[float] = Field(default=0.0, ge=0.0, le=100.0, description="Credibility score (0-100)")

    def model_dump(self, **kwargs):
        """Ensure normalized name is included"""
        data = super().model_dump(**kwargs)
        if 'name_normalized' not in data and 'name' in data:
            data['name_normalized'] = self._normalize_name(data['name'])
        return data
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for database"""
        if not name:
            return ""
        
        # Remove extra whitespace and convert to lowercase
        normalized = re.sub(r'\s+', ' ', name.strip()).lower()
        
        # Remove special characters except spaces, hyphens, and apostrophes
        normalized = re.sub(r"[^\w\s\-']", '', normalized)
        
        return normalized

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    country: Optional[str] = None
    party: Optional[str] = None
    type: Optional[str] = None
    position: Optional[str] = None
    bg_url: Optional[str] = None
    score: Optional[float] = Field(default=None, ge=0.0, le=100.0)

class ProfileResponse(BaseModel):
    id: str
    name: str
    name_normalized: str
    avatar_url: Optional[str] = None
    country: Optional[str] = None
    party: Optional[str] = None
    type: Optional[str] = "person"
    position: Optional[str] = None
    bg_url: Optional[str] = None
    score: Optional[float] = 0.0
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
                "name_normalized": normalized_name,
                "type": "person",
                "score": 0.0
            }
            
            create_response = self.supabase.table("profiles").insert(profile_data).execute()
            
            if create_response.data:
                new_profile = create_response.data[0]
                logger.info(f"Successfully created profile: ID={new_profile['id']}, Name='{new_profile['name']}'")
                return new_profile["id"]
            else:
                logger.error(f"Failed to create profile for '{name}': {create_response}")
                return None
                
        except Exception as e:
            logger.error(f"Error in get_or_create_profile for '{name}': {str(e)}")
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
            response = self.supabase.table("profiles").select("*").eq("id", profile_id).single().execute()
            
            if response.data:
                return ProfileResponse(**response.data)
            else:
                logger.warning(f"Profile not found: {profile_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting profile by ID {profile_id}: {str(e)}")
            return None

    def get_profile_by_name(self, speaker_name: str) -> Optional[dict]:
        """Get profile by speaker name using Supabase SDK"""
        try:
            normalized_name = self.normalize_name(speaker_name)
            
            if not normalized_name:
                return None
            
            response = self.supabase.table("profiles").select("*").eq("name_normalized", normalized_name).limit(1).execute()
            
            if response.data:
                profile = response.data[0]
                logger.debug(f"Found profile by name: {profile['name']} (ID: {profile['id']})")
                return profile
            else:
                logger.debug(f"No profile found for name: '{speaker_name}'")
                return None
                
        except Exception as e:
            logger.error(f"Error getting profile by name '{speaker_name}': {str(e)}")
            return None

    def create_profile(self, speaker_name: str) -> Optional[dict]:
        """Create new profile for speaker using Supabase SDK"""
        try:
            normalized_name = self.normalize_name(speaker_name)
            
            if not normalized_name:
                logger.warning(f"Cannot create profile with empty normalized name: '{speaker_name}'")
                return None
            
            profile_data = {
                "name": speaker_name.strip(),
                "name_normalized": normalized_name,
                "type": "person",
                "score": 0.0
            }
            
            response = self.supabase.table("profiles").insert(profile_data).execute()
            
            if response.data:
                new_profile = response.data[0]
                logger.info(f"Created new profile: {new_profile['name']} (ID: {new_profile['id']})")
                return new_profile
            else:
                logger.error(f"Failed to create profile for '{speaker_name}': {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating profile for '{speaker_name}': {str(e)}")
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
            update_data = updates.model_dump(exclude_none=True)
            
            # Add normalized name if name is being updated
            if 'name' in update_data:
                update_data['name_normalized'] = self.normalize_name(update_data['name'])
            
            response = self.supabase.table("profiles").update(update_data).eq("id", profile_id).execute()
            
            if response.data:
                return ProfileResponse(**response.data[0])
            else:
                logger.error(f"Failed to update profile {profile_id}: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating profile {profile_id}: {str(e)}")
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
            response = self.supabase.table("profiles").delete().eq("id", profile_id).execute()
            
            if response.data:
                logger.info(f"Successfully deleted profile: {profile_id}")
                return True
            else:
                logger.error(f"Failed to delete profile {profile_id}: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting profile {profile_id}: {str(e)}")
            return False

    def search_profiles(
        self,
        search_text: Optional[str] = None,
        country: Optional[str] = None,
        party: Optional[str] = None,
        profile_type: Optional[str] = None,
        include_statement_counts: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[ProfileResponse]:
        """
        Search profiles with optional filters.
        
        Args:
            search_text: Text to search in names
            country: Filter by country code
            party: Filter by party
            profile_type: Filter by profile type
            include_statement_counts: Whether to include statement counts
            limit: Maximum results to return
            offset: Number of results to skip
            
        Returns:
            List of profiles
        """
        try:
            query = self.supabase.table("profiles").select("*")
            
            # Apply filters
            if search_text:
                query = query.ilike("name", f"%{search_text}%")
            if country:
                query = query.eq("country", country)
            if party:
                query = query.eq("party", party)
            if profile_type:
                query = query.eq("type", profile_type)
            
            # Apply pagination
            query = query.range(offset, offset + limit - 1)
            
            response = query.execute()
            
            if response.data:
                return [ProfileResponse(**profile) for profile in response.data]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error searching profiles: {str(e)}")
            return []

    def process_speaker_profile(self, speaker_name: str) -> Optional[str]:
        """
        Process speaker profile and return profile ID
        This method uses the existing get_or_create_profile functionality
        
        Args:
            speaker_name: Name of the speaker
            
        Returns:
            Profile ID if successful, None otherwise
        """
        try:
            return self.get_or_create_profile(speaker_name)
        except Exception as e:
            logger.error(f"Error processing speaker profile '{speaker_name}': {str(e)}")
            return None

# Create service instance
profile_service = ProfileService()