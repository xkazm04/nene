from fastapi import APIRouter, Query, HTTPException
from fastapi_cache.decorator import cache
from typing import List, Optional, Dict, Any
from supabase import create_client, Client
from models.video_models import Video, VideoWithTimestamps, VideoTimestamp
import logging
import os

router = APIRouter(tags=["videos"])
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

def parse_supabase_response(data: List[Dict[str, Any]]) -> List[Video]:
    """Parse Supabase response into Video models."""
    videos = []
    for row in data:
        video = Video(
            id=str(row.get('id', '')),
            video_url=row.get('video_url', ''),
            source=row.get('source', ''),
            researched=row.get('researched', False),
            title=row.get('title'),
            verdict=row.get('verdict'),
            duration_seconds=row.get('duration_seconds'),
            speaker_name=row.get('speaker_name'),
            language_code=row.get('language_code'),
            audio_extracted=row.get('audio_extracted', False),
            transcribed=row.get('transcribed', False),
            analyzed=row.get('analyzed', False),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
            processed_at=row.get('processed_at')
        )
        videos.append(video)
    return videos

@router.get("/", response_model=List[Video])
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
    Includes cross-table filtering by timestamp categories.
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
            # Supabase doesn't support OR conditions directly in the query builder
            # We'll need to use the textSearch or implement multiple queries
            search_queries = []
            
            # Search in title
            if search:
                title_query = supabase.table('videos').select('*').ilike('title', f'%{search}%')
                speaker_query = supabase.table('videos').select('*').ilike('speaker_name', f'%{search}%')
                url_query = supabase.table('videos').select('*').ilike('video_url', f'%{search}%')
                verdict_query = supabase.table('videos').select('*').ilike('verdict', f'%{search}%')
                
                # Execute search queries
                search_results = []
                for search_query in [title_query, speaker_query, url_query, verdict_query]:
                    try:
                        result = search_query.execute()
                        search_results.extend(result.data)
                    except Exception as e:
                        logger.warning(f"Search query failed: {e}")
                
                # Get unique video IDs from search results
                if search_results:
                    search_video_ids = list(set([row['id'] for row in search_results]))
                    query = query.in_('id', search_video_ids)
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

@router.get("/{video_id}", response_model=VideoWithTimestamps)
@cache(expire=600)  # Cache for 10 minutes
async def get_video_with_timestamps(video_id: str):
    """
    Get a specific video with all its timestamps.
    """
    try:
        # Get the video
        video_result = supabase.table('videos').select('*').eq('id', video_id).execute()
        
        if not video_result.data:
            raise HTTPException(status_code=404, detail="Video not found")
        
        video_data = video_result.data[0]
        video = Video(
            id=str(video_data['id']),
            video_url=video_data['video_url'],
            source=video_data['source'],
            researched=video_data['researched'],
            title=video_data.get('title'),
            verdict=video_data.get('verdict'),
            duration_seconds=video_data.get('duration_seconds'),
            speaker_name=video_data.get('speaker_name'),
            language_code=video_data.get('language_code'),
            audio_extracted=video_data.get('audio_extracted', False),
            transcribed=video_data.get('transcribed', False),
            analyzed=video_data.get('analyzed', False),
            created_at=video_data.get('created_at'),
            updated_at=video_data.get('updated_at'),
            processed_at=video_data.get('processed_at')
        )
        
        # Get timestamps for this video
        timestamps_result = supabase.table('video_timestamps').select('*').eq('video_id', video_id).order('time_from_seconds').execute()
        
        timestamps = []
        if timestamps_result.data:
            for ts_data in timestamps_result.data:
                timestamp = VideoTimestamp(
                    id=str(ts_data['id']),
                    video_id=str(ts_data['video_id']),
                    research_id=ts_data.get('research_id'),
                    time_from_seconds=ts_data['time_from_seconds'],
                    time_to_seconds=ts_data['time_to_seconds'],
                    statement=ts_data['statement'],
                    context=ts_data.get('context'),
                    category=ts_data.get('category'),
                    confidence_score=ts_data.get('confidence_score'),
                    created_at=ts_data.get('created_at')
                )
                timestamps.append(timestamp)
        
        return VideoWithTimestamps(video=video, timestamps=timestamps)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve video: {str(e)}")

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

@router.get("/categories/available")
@cache(expire=1800)  # Cache for 30 minutes
async def get_available_categories():
    """
    Get all available categories from video timestamps.
    """
    try:
        result = supabase.table('video_timestamps').select('category').execute()
        
        if not result.data:
            return []
        
        # Get unique categories, excluding null values
        categories = list(set([
            row['category'] for row in result.data 
            if row.get('category') is not None
        ]))
        
        # Return sorted list with category counts
        category_stats = {}
        for row in result.data:
            if row.get('category'):
                category_stats[row['category']] = category_stats.get(row['category'], 0) + 1
        
        return [
            {
                "category": category,
                "count": category_stats.get(category, 0)
            }
            for category in sorted(categories)
        ]
        
    except Exception as e:
        logger.error(f"Error getting available categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get categories")