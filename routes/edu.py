from fastapi import APIRouter, HTTPException, Query
from fastapi_cache.decorator import cache
from typing import List, Optional, Dict, Any
from supabase import create_client, Client
import logging
import os
from services.edu.timeline import parse_timeline_response, parse_timeline_detail_response   

router = APIRouter(tags=["education"])
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)



@router.get("/timelines", response_model=List[Dict[str, Any]])
@cache(expire=600)  # Cache for 10 minutes
async def get_timelines(
    limit: int = Query(default=50, ge=1, le=100, description="Number of timelines to return"),
    offset: int = Query(default=0, ge=0, description="Number of timelines to skip"),
    search: Optional[str] = Query(default=None, description="Search in title or question")
):
    """
    Get all educational timelines (basic info only).
    """
    try:
        # Start with base query
        query = supabase.table('edu_timeline').select(
            'id, title, question, dimension_top_title, dimension_bottom_title, created_at, updated_at'
        )
        
        # Apply search if provided
        if search:
            # Search in title and question
            query = query.or_(f'title.ilike.%{search}%,question.ilike.%{search}%')
        
        # Add ordering and pagination
        query = query.order('created_at', desc=True).range(offset, offset + limit - 1)
        
        # Execute query
        result = query.execute()
        
        if result.data is None:
            logger.warning("No timeline data returned from Supabase query")
            return []
        
        timelines = parse_timeline_response(result.data)
        
        logger.info(f"Retrieved {len(timelines)} timelines")
        return timelines
        
    except Exception as e:
        logger.error(f"Error retrieving timelines: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve timelines: {str(e)}")

@router.get("/timelines/{timeline_id}", response_model=Dict[str, Any])
@cache(expire=600)  # Cache for 10 minutes
async def get_timeline_detail(timeline_id: str):
    """
    Get a specific timeline with all milestones and events.
    """
    try:
        # Get timeline basic info
        timeline_result = supabase.table('edu_timeline').select('*').eq('id', timeline_id).execute()
        
        if not timeline_result.data:
            raise HTTPException(status_code=404, detail="Timeline not found")
        
        timeline_data = timeline_result.data[0]
        
        # Get milestones for this timeline
        milestones_result = supabase.table('edu_milestone').select('*').eq('timeline_id', timeline_id).order('order_index').execute()
        
        if not milestones_result.data:
            # Timeline exists but has no milestones
            return parse_timeline_detail_response(timeline_data, [], [])
        
        milestones_data = milestones_result.data
        milestone_ids = [str(m['id']) for m in milestones_data]
        
        # Get events for all milestones
        events_result = supabase.table('edu_event').select('*').in_('milestone_id', milestone_ids).order('milestone_id, order_index').execute()
        
        events_data = events_result.data if events_result.data else []
        
        # Parse and return the complete timeline
        timeline_detail = parse_timeline_detail_response(timeline_data, milestones_data, events_data)
        
        logger.info(f"Retrieved timeline {timeline_id} with {len(milestones_data)} milestones and {len(events_data)} events")
        return timeline_detail
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving timeline {timeline_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve timeline: {str(e)}")

@router.get("/timelines/{timeline_id}/milestones", response_model=List[Dict[str, Any]])
@cache(expire=600)
async def get_timeline_milestones(timeline_id: str):
    """
    Get milestones for a specific timeline (without events).
    """
    try:
        # Verify timeline exists
        timeline_check = supabase.table('edu_timeline').select('id').eq('id', timeline_id).execute()
        if not timeline_check.data:
            raise HTTPException(status_code=404, detail="Timeline not found")
        
        # Get milestones
        result = supabase.table('edu_milestone').select('*').eq('timeline_id', timeline_id).order('order_index').execute()
        
        milestones = []
        for milestone in result.data if result.data else []:
            milestone_obj = {
                "id": str(milestone['id']),
                "timeline_id": str(milestone['timeline_id']),
                "date": milestone['date'],
                "order": milestone['order_index'],
                "is_top": milestone['is_top'],
                "created_at": milestone['created_at'],
                "updated_at": milestone['updated_at']
            }
            milestones.append(milestone_obj)
        
        return milestones
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving milestones for timeline {timeline_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve milestones: {str(e)}")

@router.get("/stats/summary")
@cache(expire=1800)  # Cache for 30 minutes
async def get_education_stats():
    """
    Get summary statistics about educational content.
    """
    try:
        # Get timeline count
        timelines_result = supabase.table('edu_timeline').select('id, created_at').execute()
        timelines_count = len(timelines_result.data) if timelines_result.data else 0
        
        # Get milestone count
        milestones_result = supabase.table('edu_milestone').select('id').execute()
        milestones_count = len(milestones_result.data) if milestones_result.data else 0
        
        # Get event count
        events_result = supabase.table('edu_event').select('id').execute()
        events_count = len(events_result.data) if events_result.data else 0
        
        # Calculate dates
        creation_dates = [t.get('created_at') for t in (timelines_result.data or []) if t.get('created_at')]
        earliest_timeline = min(creation_dates) if creation_dates else None
        latest_timeline = max(creation_dates) if creation_dates else None
        
        return {
            "total_timelines": timelines_count,
            "total_milestones": milestones_count,
            "total_events": events_count,
            "average_milestones_per_timeline": round(milestones_count / timelines_count, 2) if timelines_count > 0 else 0,
            "average_events_per_milestone": round(events_count / milestones_count, 2) if milestones_count > 0 else 0,
            "earliest_timeline": earliest_timeline,
            "latest_timeline": latest_timeline
        }
        
    except Exception as e:
        logger.error(f"Error getting education stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")