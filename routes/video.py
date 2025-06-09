from fastapi import APIRouter, HTTPException
from fastapi_cache.decorator import cache
from supabase import create_client, Client
from models.video_models import (
    VideoDetailResponse, TimestampWithResearch, ResearchResult
)
import logging
import os

router = APIRouter(tags=["video-detail"])
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

def safe_uuid_convert(value):
    """Safely convert UUID values to strings for comparison"""
    if value is None:
        return None
    return str(value)

def validate_video_data(video_data):
    """Validate and clean video data"""
    return {
        'video_url': video_data.get('video_url', ''),
        'source': video_data.get('source', 'unknown'),
        'title': video_data.get('title'),
        'verdict': video_data.get('verdict'),
        'duration_seconds': int(video_data['duration_seconds']) if video_data.get('duration_seconds') else None,
        'speaker_name': video_data.get('speaker_name'),
        'language_code': video_data.get('language_code'),
        'processed_at': video_data.get('processed_at')
    }

@router.get("/{video_id}", response_model=VideoDetailResponse)
async def get_video_detail(video_id: str):
    """
    Get comprehensive video details with timestamps and research results.
    
    This route combines data from three tables:
    1. videos - base video information
    2. video_timestamps - statement timing data  
    3. research_results - fact-checking results (when available)
    
    Returns a unified response perfect for frontend consumption.
    """
    try:
        logger.info(f"Fetching video details for ID: {video_id}")
        
        # Step 1: Get the base video data
        video_result = supabase.table('videos').select('*').eq('id', video_id).execute()
        
        if not video_result.data:
            logger.warning(f"Video not found: {video_id}")
            raise HTTPException(status_code=404, detail="Video not found")
        
        video_data = video_result.data[0]
        logger.info(f"Found video: {video_data.get('title', 'Untitled')} by {video_data.get('speaker_name', 'Unknown')}")
        
        # Validate and clean video data
        clean_video_data = validate_video_data(video_data)
        
        # Step 2: Get video timestamps (ordered by time)
        logger.info("Fetching video timestamps...")
        timestamps_result = supabase.table('video_timestamps').select('*').eq('video_id', video_id).order('time_from_seconds').execute()
        
        if not timestamps_result.data:
            logger.info("No timestamps found for this video")
            # Return video with empty timestamps
            response = VideoDetailResponse(
                video_url=video_data['video_url'],
                source=video_data['source'],
                title=video_data.get('title'),
                verdict=video_data.get('verdict'),
                duration_seconds=video_data.get('duration_seconds'),
                speaker_name=video_data.get('speaker_name'),
                language_code=video_data.get('language_code'),
                processed_at=video_data.get('processed_at'),
                timestamps=[],
                total_statements=0,
                researched_statements=0,
                research_completion_rate=0.0
            )
            return response
        
        # Step 3: Get research results for timestamps that have research_id
        logger.info(f"Found {len(timestamps_result.data)} timestamps")
        
        # Convert research IDs to strings and filter out None values
        research_ids = []
        for ts in timestamps_result.data:
            research_id = ts.get('research_id')
            if research_id:
                research_ids.append(safe_uuid_convert(research_id))
        
        logger.info(f"Found {len(research_ids)} timestamps with research IDs: {research_ids}")
        
        research_data = {}
        if research_ids:
            logger.info("Fetching research results...")
            try:
                research_result = supabase.table('research_results').select('*').in_('id', research_ids).execute()
                
                if research_result.data:
                    # Create lookup dictionary for research data
                    research_data = {safe_uuid_convert(r['id']): r for r in research_result.data}
                    logger.info(f"Fetched {len(research_data)} research results")
                else:
                    logger.warning("No research results found despite having research IDs")
            except Exception as research_error:
                logger.error(f"Error fetching research results: {research_error}")
                # Continue without research data
                research_data = {}
        
        # Step 4: Combine timestamps with research data
        logger.info("Combining timestamp and research data...")
        combined_timestamps = []
        total_statements = 0
        researched_statements = 0
        
        for ts_data in timestamps_result.data:
            total_statements += 1
            
            # Get research data if exists
            research = None
            research_id = safe_uuid_convert(ts_data.get('research_id'))
            
            if research_id and research_id in research_data:
                researched_statements += 1
                r_data = research_data[research_id]
                
                logger.debug(f"Found research for statement: {ts_data['statement'][:50]}...")
                
                try:
                    research = ResearchResult(
                        id=safe_uuid_convert(r_data['id']),
                        source=r_data.get('source'),
                        country=r_data.get('country'),
                        valid_sources=r_data.get('valid_sources'),
                        verdict=r_data.get('verdict'),
                        status=r_data.get('status'),
                        correction=r_data.get('correction'),
                        resources_agreed=r_data.get('resources_agreed'),
                        resources_disagreed=r_data.get('resources_disagreed'),
                        experts=r_data.get('experts'),
                        processed_at=r_data.get('processed_at')
                    )
                except Exception as research_build_error:
                    logger.error(f"Error building research object: {research_build_error}")
                    research = None
            
            # Build combined timestamp
            try:
                timestamp = TimestampWithResearch(
                    time_from_seconds=int(ts_data['time_from_seconds']) if ts_data.get('time_from_seconds') else 0,
                    time_to_seconds=int(ts_data['time_to_seconds']) if ts_data.get('time_to_seconds') else 0,
                    statement=str(ts_data['statement']) if ts_data.get('statement') else "",
                    context=ts_data.get('context'),
                    category=ts_data.get('category'),
                    confidence_score=float(ts_data['confidence_score']) if ts_data.get('confidence_score') else None,
                    research=research
                )
                combined_timestamps.append(timestamp)
            except Exception as timestamp_build_error:
                logger.error(f"Error building timestamp object: {timestamp_build_error}")
                logger.error(f"Timestamp data: {ts_data}")
                # Skip this timestamp and continue
                total_statements -= 1
                continue
        
        # Step 5: Calculate completion rate
        research_completion_rate = (researched_statements / total_statements * 100) if total_statements > 0 else 0.0
        
        # Step 6: Build final response
        response = VideoDetailResponse(
            video_url=video_data['video_url'],
            source=video_data['source'],
            title=video_data.get('title'),
            verdict=video_data.get('verdict'),
            duration_seconds=video_data.get('duration_seconds'),
            speaker_name=video_data.get('speaker_name'),
            language_code=video_data.get('language_code'),
            processed_at=video_data.get('processed_at'),
            timestamps=combined_timestamps,
            total_statements=total_statements,
            researched_statements=researched_statements,
            research_completion_rate=round(research_completion_rate, 1)
        )
        
        logger.info(f"Video detail response prepared:")
        logger.info(f"  - Video title: {video_data.get('title', 'Untitled')}")
        logger.info(f"  - Speaker: {video_data.get('speaker_name', 'Unknown')}")
        logger.info(f"  - Total statements: {total_statements}")
        logger.info(f"  - Researched statements: {researched_statements}")
        logger.info(f"  - Completion rate: {research_completion_rate:.1f}%")
        logger.info(f"  - Duration: {video_data.get('duration_seconds', 0)}s")
        logger.info(f"  - Language: {video_data.get('language_code', 'unknown')}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving video details for {video_id}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve video details: {str(e)}"
        )