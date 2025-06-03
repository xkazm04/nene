from fastapi import APIRouter, HTTPException
from supabase import create_client, Client
import os
import logging

router = APIRouter(tags=["debug"])
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

@router.get("/connection")
async def test_connection():
    """Test Supabase connection and basic queries."""
    try:
        # Test basic connection
        result = supabase.table('videos').select('count', count='exact').execute()
        videos_count = result.count if result.count is not None else 0
        
        # Test research_results table
        research_result = supabase.table('research_results').select('count', count='exact').execute()
        research_count = research_result.count if research_result.count is not None else 0
        
        # Test video_timestamps table
        timestamps_result = supabase.table('video_timestamps').select('count', count='exact').execute()
        timestamps_count = timestamps_result.count if timestamps_result.count is not None else 0
        
        return {
            "status": "connected",
            "supabase_url": supabase_url[:50] + "..." if supabase_url else "NOT SET",
            "supabase_key": "SET" if supabase_key else "NOT SET",
            "tables": {
                "videos": {
                    "count": videos_count,
                    "accessible": True
                },
                "research_results": {
                    "count": research_count,
                    "accessible": True
                },
                "video_timestamps": {
                    "count": timestamps_count,
                    "accessible": True
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "supabase_url": supabase_url[:50] + "..." if supabase_url else "NOT SET",
            "supabase_key": "SET" if supabase_key else "NOT SET"
        }

@router.get("/sample-data")
async def get_sample_data():
    """Get sample data from all tables."""
    try:
        # Get sample videos
        videos_result = supabase.table('videos').select('*').limit(3).execute()
        
        # Get sample research results
        research_result = supabase.table('research_results').select('*').limit(3).execute()
        
        # Get sample timestamps
        timestamps_result = supabase.table('video_timestamps').select('*').limit(5).execute()
        
        return {
            "videos": {
                "count": len(videos_result.data) if videos_result.data else 0,
                "sample": videos_result.data[:2] if videos_result.data else []
            },
            "research_results": {
                "count": len(research_result.data) if research_result.data else 0,
                "sample": research_result.data[:2] if research_result.data else []
            },
            "video_timestamps": {
                "count": len(timestamps_result.data) if timestamps_result.data else 0,
                "sample": timestamps_result.data[:2] if timestamps_result.data else []
            }
        }
        
    except Exception as e:
        logger.error(f"Sample data retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get sample data: {str(e)}")

@router.get("/raw-query")
async def test_raw_query():
    """Test raw SQL query execution."""
    try:
        # Test with direct SQL
        result = supabase.table('videos').select('id, title, source').limit(1).execute()
        
        return {
            "query_successful": True,
            "result_data": result.data,
            "result_count": len(result.data) if result.data else 0
        }
        
    except Exception as e:
        return {
            "query_successful": False,
            "error": str(e)
        }