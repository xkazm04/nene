from fastapi import APIRouter, Query, HTTPException
from fastapi_cache.decorator import cache
from typing import List, Optional, Dict, Any
from supabase import create_client, Client
from models.video_models import Video
import logging
import os

router = APIRouter(tags=["videos"])
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

def parse_supabase_response(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse Supabase response into frontend-compatible format."""
    videos = []
    for row in data:
        # Convert to frontend-compatible format matching video_api.ts Video interface
        video = {
            "id": str(row.get('id', '')),
            "video_url": row.get('video_url', ''),
            "source": row.get('source', ''),
            "researched": row.get('researched', False),
            "title": row.get('title'),
            "verdict": row.get('verdict'),
            "duration_seconds": row.get('duration_seconds'),
            "speaker_name": row.get('speaker_name'),
            "language_code": row.get('language_code'),
            "audio_extracted": row.get('audio_extracted', False),
            "transcribed": row.get('transcribed', False),
            "analyzed": row.get('analyzed', False),
            "created_at": row.get('created_at'),
            "updated_at": row.get('updated_at'),
            "processed_at": row.get('processed_at')
        }
        videos.append(video)
    return videos

@router.get("/", response_model=List[Dict[str, Any]])
# @cache(expire=300)  # Cache for 5 minutes
async def get_videos(
    # Pagination
    limit: int = Query(default=50, ge=1, le=100, description="Number of videos to return"),
    offset: int = Query(default=0, ge=0, description="Number of videos to skip"),
    # Filtering
    source: Optional[str] = Query(default=None, description="Filter by video source (youtube, tiktok, etc.)"),
    researched: Optional[bool] = Query(default=None, description="Filter by research status"),
    analyzed: Optional[bool] = Query(default=None, description="Filter by analysis status"),
    speaker_name: Optional[str] = Query(default=None, description="Filter by speaker name"),
    language_code: Optional[str] = Query(default=None, description="Filter by language code"),
    categories: Optional[str] = Query(default=None, description="Filter by categories (comma-separated, e.g., 'HEALTHCARE,TECHNOLOGY')"),
    # Search
    search: Optional[str] = Query(default=None, description="Search in title, speaker name, or URL"),
    # Sorting
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: str = Query(default="desc", regex="^(asc|desc)$", description="Sort order")
):
    """
    Get all videos with filtering, searching, sorting and pagination.
    Returns frontend-compatible format.
    """
    try:
        # Start with base query
        query = supabase.table('videos').select(
            'id, video_url, source, researched, title, verdict, '
            'duration_seconds, speaker_name, language_code, '
            'audio_extracted, transcribed, analyzed, '
            'created_at, updated_at, processed_at'
        )
        
        # Handle category filtering (cross-table query)
        if categories:
            category_list = [cat.strip().upper() for cat in categories.split(',')]
            
            # First, get video IDs that have timestamps with the specified categories
            timestamps_query = supabase.table('video_timestamps').select('video_id').in_('category', category_list)
            timestamps_result = timestamps_query.execute()
            
            if timestamps_result.data:
                video_ids = list(set([row['video_id'] for row in timestamps_result.data]))
                query = query.in_('id', video_ids)
            else:
                # No videos match the category filter
                return []
        
        # Apply basic filters
        if source:
            query = query.eq('source', source)
            
        if researched is not None:
            query = query.eq('researched', researched)
            
        if analyzed is not None:
            query = query.eq('analyzed', analyzed)
            
        if speaker_name:
            query = query.ilike('speaker_name', f'%{speaker_name}%')
            
        if language_code:
            query = query.eq('language_code', language_code)
            
        # Add search functionality
        if search:
            # Get video IDs that match search criteria
            search_video_ids = set()
            
            # Search in multiple fields
            for field in ['title', 'speaker_name', 'video_url', 'verdict']:
                try:
                    field_query = supabase.table('videos').select('id').ilike(field, f'%{search}%')
                    result = field_query.execute()
                    if result.data:
                        search_video_ids.update([row['id'] for row in result.data])
                except Exception as e:
                    logger.warning(f"Search query failed for field {field}: {e}")
            
            if search_video_ids:
                query = query.in_('id', list(search_video_ids))
            else:
                return []
        
        # Add sorting
        valid_sort_fields = {
            "created_at", "updated_at", "processed_at", "title", 
            "speaker_name", "duration_seconds", "source"
        }
        if sort_by not in valid_sort_fields:
            sort_by = "created_at"
        
        if sort_order == "desc":
            query = query.order(sort_by, desc=True)
        else:
            query = query.order(sort_by, desc=False)
        
        # Add pagination
        query = query.range(offset, offset + limit - 1)
        
        # Execute query
        result = query.execute()
        
        if result.data is None:
            logger.warning("No data returned from Supabase query")
            return []
        
        videos = parse_supabase_response(result.data)
        
        logger.info(f"Retrieved {len(videos)} videos with filters: source={source}, researched={researched}, categories={categories}")
        return videos
        
    except Exception as e:
        logger.error(f"Error retrieving videos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve videos: {str(e)}")



@router.get("/search/advanced")
@cache(expire=300)
async def search_videos_advanced(
    search_text: Optional[str] = Query(default=None, description="Search text"),
    source_filter: Optional[str] = Query(default=None, description="Source filter"),
    researched_filter: Optional[bool] = Query(default=None, description="Research status filter"),
    speaker_filter: Optional[str] = Query(default=None, description="Speaker filter"),
    language_filter: Optional[str] = Query(default=None, description="Language filter"),
    categories_filter: Optional[str] = Query(default=None, description="Categories filter (comma-separated)"),
    limit_count: int = Query(default=50, ge=1, le=100, description="Limit results"),
    offset_count: int = Query(default=0, ge=0, description="Offset results")
):
    """
    Advanced search with full-text search capabilities and category filtering.
    """
    try:
        # Start with base query including joins for category search
        query = supabase.table('videos').select(
            'id, video_url, source, title, speaker_name, '
            'researched, analyzed, duration_seconds, processed_at, '
            'video_timestamps(category)'
        )
        
        # Apply filters
        if source_filter:
            query = query.eq('source', source_filter)
            
        if researched_filter is not None:
            query = query.eq('researched', researched_filter)
            
        if speaker_filter:
            query = query.ilike('speaker_name', f'%{speaker_filter}%')
            
        if language_filter:
            query = query.eq('language_code', language_filter)
        
        # Handle category filtering
        if categories_filter:
            category_list = [cat.strip().upper() for cat in categories_filter.split(',')]
            # Get video IDs that have timestamps with specified categories
            timestamps_query = supabase.table('video_timestamps').select('video_id').in_('category', category_list)
            timestamps_result = timestamps_query.execute()
            
            if timestamps_result.data:
                video_ids = list(set([row['video_id'] for row in timestamps_result.data]))
                query = query.in_('id', video_ids)
            else:
                return []
        
        # Apply text search if provided
        if search_text:
            # Implement multi-field search
            search_queries = []
            for field in ['title', 'speaker_name', 'video_url', 'verdict']:
                field_query = supabase.table('videos').select('id').ilike(field, f'%{search_text}%')
                try:
                    result = field_query.execute()
                    search_queries.extend([row['id'] for row in result.data])
                except Exception as e:
                    logger.warning(f"Search in {field} failed: {e}")
            
            if search_queries:
                unique_ids = list(set(search_queries))
                query = query.in_('id', unique_ids)
            else:
                return []
        
        # Add pagination and execute
        query = query.range(offset_count, offset_count + limit_count - 1)
        result = query.execute()
        
        if not result.data:
            return []
        
        # Process results with category aggregation
        videos = []
        for row in result.data:
            # Count statements and get categories
            timestamps_info = row.get('video_timestamps', [])
            total_statements = len(timestamps_info)
            categories = list(set([ts.get('category') for ts in timestamps_info if ts.get('category')]))
            
            video_data = {
                "id": str(row['id']),
                "video_url": row['video_url'],
                "source": row['source'],
                "title": row.get('title'),
                "speaker_name": row.get('speaker_name'),
                "total_statements": total_statements,
                "researched_statements": total_statements if row.get('researched') else 0,
                "categories": categories,
                "processed_at": row.get('processed_at'),
                "match_rank": 1.0  # Simple ranking, can be enhanced
            }
            videos.append(video_data)
        
        return videos
        
    except Exception as e:
        logger.error(f"Error in advanced search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/stats/summary")
@cache(expire=600)
async def get_video_stats():
    """
    Get summary statistics about videos including category distribution.
    """
    try:
        # Get basic video stats
        videos_result = supabase.table('videos').select(
            'id, source, researched, analyzed, duration_seconds, '
            'speaker_name, language_code, created_at'
        ).execute()
        
        if not videos_result.data:
            return {
                "total_videos": 0,
                "researched_videos": 0,
                "analyzed_videos": 0,
                "unique_sources": 0,
                "unique_speakers": 0,
                "unique_languages": 0,
                "avg_duration_seconds": 0,
                "category_distribution": {},
                "earliest_video": None,
                "latest_video": None
            }
        
        videos_data = videos_result.data
        
        # Get category distribution from timestamps
        timestamps_result = supabase.table('video_timestamps').select('category').execute()
        categories = [ts['category'] for ts in timestamps_result.data if ts.get('category')]
        category_distribution = {}
        for category in categories:
            category_distribution[category] = category_distribution.get(category, 0) + 1
        
        # Calculate statistics
        total_videos = len(videos_data)
        researched_videos = sum(1 for v in videos_data if v.get('researched'))
        analyzed_videos = sum(1 for v in videos_data if v.get('analyzed'))
        unique_sources = len(set(v.get('source') for v in videos_data if v.get('source')))
        unique_speakers = len(set(v.get('speaker_name') for v in videos_data if v.get('speaker_name')))
        unique_languages = len(set(v.get('language_code') for v in videos_data if v.get('language_code')))
        
        durations = [v.get('duration_seconds') for v in videos_data if v.get('duration_seconds')]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        created_dates = [v.get('created_at') for v in videos_data if v.get('created_at')]
        earliest_video = min(created_dates) if created_dates else None
        latest_video = max(created_dates) if created_dates else None
        
        return {
            "total_videos": total_videos,
            "researched_videos": researched_videos,
            "analyzed_videos": analyzed_videos,
            "unique_sources": unique_sources,
            "unique_speakers": unique_speakers,
            "unique_languages": unique_languages,
            "avg_duration_seconds": avg_duration,
            "category_distribution": category_distribution,
            "earliest_video": earliest_video,
            "latest_video": latest_video
        }
        
    except Exception as e:
        logger.error(f"Error getting video stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")