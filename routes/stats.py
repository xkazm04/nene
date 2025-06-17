from fastapi import APIRouter, HTTPException, Path
import logging
from services.stats import stats_service
from models.stats_models import ProfileStatsResponse
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(tags=["statistics"])

@router.get("/profile/{profile_id}", response_model=ProfileStatsResponse)
async def get_profile_stats(
    profile_id: str = Path(..., description="Profile UUID", min_length=36, max_length=36)
) -> ProfileStatsResponse:
    """
    Get comprehensive statistics for a specific profile.
    
    This endpoint provides:
    - Last 10 statements with key attributes (verdict, status, category, etc.)
    - Total statement count
    - Breakdown by categories (only categories with statements > 0)
    - Breakdown by status (TRUE, FALSE, MISLEADING, etc.)
    
    Args:
        profile_id: Profile UUID
        
    Returns:
        ProfileStatsResponse: Complete statistics including recent statements and breakdowns
        
    Raises:
        HTTPException: If profile not found or retrieval fails
    """
    try:
        # Validate UUID format
        try:
            uuid.UUID(profile_id)
        except ValueError:
            logger.warning(f"Invalid UUID format: {profile_id} (length: {len(profile_id)})")
            raise HTTPException(status_code=400, detail=f"Invalid UUID format: {profile_id}")
        
        logger.info(f"Retrieving statistics for profile: {profile_id}")
        
        stats = stats_service.get_profile_stats(profile_id)
        
        if not stats:
            logger.warning(f"Profile stats not found: {profile_id}")
            raise HTTPException(status_code=404, detail="Profile not found or no statistics available")
        
        logger.info(f"Successfully retrieved stats for profile: {profile_id} - {stats.stats.total_statements} statements")
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to retrieve profile statistics: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/profile/{profile_id}/summary")
async def get_profile_stats_summary(
    profile_id: str = Path(..., description="Profile UUID", min_length=36, max_length=36)
):
    """
    Get quick summary statistics for a profile.
    
    Args:
        profile_id: Profile UUID
        
    Returns:
        Dict with summary statistics
    """
    try:
        # Validate UUID format
        try:
            uuid.UUID(profile_id)
        except ValueError:
            logger.warning(f"Invalid UUID format: {profile_id} (length: {len(profile_id)})")
            raise HTTPException(status_code=400, detail=f"Invalid UUID format: {profile_id}")
            
        logger.info(f"Retrieving summary stats for profile: {profile_id}")
        
        total_count = stats_service.get_profile_statement_count(profile_id)
        category_breakdown = stats_service.get_category_breakdown(profile_id)
        
        # Calculate some quick stats
        top_category = max(category_breakdown.items(), key=lambda x: x[1]) if category_breakdown else ("none", 0)
        
        summary = {
            "profile_id": profile_id,
            "total_statements": total_count,
            "categories_count": len(category_breakdown),
            "top_category": {
                "name": top_category[0],
                "count": top_category[1]
            },
            "category_breakdown": category_breakdown
        }
        
        logger.info(f"Successfully retrieved summary for profile: {profile_id}")
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to retrieve profile summary: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)