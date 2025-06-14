from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging
from services.profile import (
    profile_service, 
    ProfileCreate, 
    ProfileUpdate, 
    ProfileResponse
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["profiles"])

@router.post("/", response_model=ProfileResponse)
async def create_profile(profile: ProfileCreate) -> ProfileResponse:
    """
    Create a new profile.
    
    Args:
        profile: Profile creation data
        
    Returns:
        ProfileResponse: Created profile data
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info(f"Creating profile for: {profile.name}")
        
        # Try to get existing profile first
        existing_id = profile_service.get_or_create_profile(profile.name)
        if existing_id:
            # Get the existing profile details
            existing_profile = profile_service.get_profile_by_id(existing_id)
            if existing_profile:
                logger.info(f"Profile already exists: {profile.name} -> {existing_id}")
                return existing_profile
        
        # If we get here, something went wrong with get_or_create
        raise HTTPException(status_code=500, detail="Failed to create profile")
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to create profile: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: str) -> ProfileResponse:
    """
    Get profile by ID with statement count.
    
    Args:
        profile_id: Profile UUID
        
    Returns:
        ProfileResponse: Profile data with total_statements count
        
    Raises:
        HTTPException: If profile not found
    """
    try:
        logger.info(f"Retrieving profile: {profile_id}")
        
        profile = profile_service.get_profile_by_id(profile_id)
        
        if not profile:
            logger.warning(f"Profile not found: {profile_id}")
            raise HTTPException(status_code=404, detail="Profile not found")
        
        logger.info(f"Successfully retrieved profile: {profile_id} with {profile.total_statements} statements")
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to retrieve profile: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.patch("/{profile_id}", response_model=ProfileResponse)
async def update_profile(profile_id: str, updates: ProfileUpdate) -> ProfileResponse:
    """
    Update profile by ID.
    
    Args:
        profile_id: Profile UUID
        updates: Fields to update
        
    Returns:
        ProfileResponse: Updated profile data with statement count
        
    Raises:
        HTTPException: If profile not found or update fails
    """
    try:
        logger.info(f"Updating profile: {profile_id}")
        
        updated_profile = profile_service.update_profile(profile_id, updates)
        
        if not updated_profile:
            logger.warning(f"Profile not found or update failed: {profile_id}")
            raise HTTPException(status_code=404, detail="Profile not found or update failed")
        
        logger.info(f"Successfully updated profile: {profile_id}")
        return updated_profile
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to update profile: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

@router.delete("/{profile_id}")
async def delete_profile(profile_id: str):
    """
    Delete profile by ID.
    
    Args:
        profile_id: Profile UUID
        
    Returns:
        Dict with success message
        
    Raises:
        HTTPException: If profile not found or deletion fails
    """
    try:
        logger.info(f"Deleting profile: {profile_id}")
        
        success = profile_service.delete_profile(profile_id)
        
        if not success:
            logger.warning(f"Profile not found or deletion failed: {profile_id}")
            raise HTTPException(status_code=404, detail="Profile not found or deletion failed")
        
        logger.info(f"Successfully deleted profile: {profile_id}")
        return {"message": "Profile deleted successfully", "profile_id": profile_id}
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to delete profile: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/", response_model=List[ProfileResponse])
async def search_profiles(
    search: Optional[str] = Query(None, description="Search text for names"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    party: Optional[str] = Query(None, description="Filter by party"),
    include_counts: bool = Query(False, description="Include statement counts (slower)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
) -> List[ProfileResponse]:
    """
    Search profiles with optional filters.
    
    Args:
        search: Text to search in names
        country: Filter by country code  
        party: Filter by party
        include_counts: Whether to include statement counts
        limit: Maximum results to return
        offset: Number of results to skip
        
    Returns:
        List of profiles
    """
    try:
        logger.info(f"Searching profiles: search='{search}', country='{country}', party='{party}', include_counts={include_counts}")
        
        profiles = profile_service.search_profiles(
            search_text=search,
            country=country,
            party=party,
            include_statement_counts=True,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"Found {len(profiles)} profiles")
        return profiles
        
    except Exception as e:
        error_msg = f"Failed to search profiles: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
