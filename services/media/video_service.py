import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from models.video_models import TimestampEstimate
from models.processing_models import ProcessingUpdate, ProcessingStatus
from services.sse_service import sse_service

load_dotenv()
logger = logging.getLogger(__name__)

class VideoService:
    """Service for managing video records and timestamps in the database."""
    
    def __init__(self):
        """Initialize Supabase client with credentials from environment."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")
        
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Video service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            raise
    
    def create_video_record(
        self, 
        video_url: str, 
        source: str = "youtube", 
        frontend_mode: bool = False,
        job_id: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Create a new video record in the database.
        
        Args:
            video_url: The video URL
            source: Video source platform (youtube, tiktok, etc.)
            frontend_mode: Whether called from frontend (enables SSE)
            job_id: Processing job ID for SSE updates
            **kwargs: Additional video metadata
            
        Returns:
            str: Video ID if successful, None otherwise
        """
        try:
            logger.info(f"Creating video record for URL: {video_url}")
            
            # Check if video already exists
            existing = self.get_video_by_url(video_url)
            if existing:
                logger.info(f"Video already exists with ID: {existing['id']}")
                
                # Send SSE update if in frontend mode
                if frontend_mode and job_id:
                    update = ProcessingUpdate(
                        job_id=job_id,
                        video_id=existing['id'],
                        status=ProcessingStatus.DOWNLOADING,
                        step="Video record found",
                        progress=10,
                        message=f"Video record already exists",
                        timestamp=datetime.utcnow()
                    )
                    asyncio.create_task(sse_service.broadcast_update(job_id, update))
                
                return existing['id']
            
            # Prepare video data
            video_data = {
                "video_url": video_url,
                "source": source,
                **kwargs
            }
            
            response = self.supabase.table("videos").insert(video_data).execute()
            
            if not response.data:
                raise Exception("No data returned from video insert")
            
            video_id = response.data[0]["id"]
            logger.info(f"Video record created with ID: {video_id}")
            
            # Send SSE update if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.DOWNLOADING,
                    step="Video record created",
                    progress=15,
                    message=f"Video record created successfully",
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            return video_id
            
        except Exception as e:
            logger.error(f"Failed to create video record: {str(e)}")
            
            # Send SSE error if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    status=ProcessingStatus.FAILED,
                    step="Video record creation",
                    progress=0,
                    message="Failed to create video record",
                    error=str(e),
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            return None
    
    def update_video_status(
        self, 
        video_id: str, 
        frontend_mode: bool = False,
        job_id: Optional[str] = None,
        progress: Optional[int] = None,
        step_message: Optional[str] = None,
        **status_updates
    ) -> bool:
        """
        Update video processing status.
        
        Args:
            video_id: Video ID
            frontend_mode: Whether called from frontend (enables SSE)
            job_id: Processing job ID for SSE updates
            progress: Progress percentage (0-100)
            step_message: Step description for SSE
            **status_updates: Status fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.debug(f"Updating video status for {video_id}: {status_updates}")
            
            response = self.supabase.table("videos").update(status_updates).eq("id", video_id).execute()
            
            if response.data:
                logger.debug(f"Video status updated successfully")
                
                # Send SSE update if in frontend mode
                if frontend_mode and job_id and step_message:
                    # Determine status based on updates
                    status = ProcessingStatus.DOWNLOADING
                    if status_updates.get('transcribed'):
                        status = ProcessingStatus.TRANSCRIBING
                    elif status_updates.get('analyzed'):
                        status = ProcessingStatus.ANALYZING
                    
                    update = ProcessingUpdate(
                        job_id=job_id,
                        video_id=video_id,
                        status=status,
                        step=step_message,
                        progress=progress or 50,
                        message=f"Video status updated: {step_message}",
                        timestamp=datetime.utcnow()
                    )
                    asyncio.create_task(sse_service.broadcast_update(job_id, update))
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update video status: {str(e)}")
            return False

    def get_video_by_url(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Get video record by URL."""
        try:
            response = self.supabase.table("videos").select("*").eq("video_url", video_url).limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get video by URL: {str(e)}")
            return None

    def get_video_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video record by ID."""
        try:
            response = self.supabase.table("videos").select("*").eq("id", video_id).limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get video by ID: {str(e)}")
            return None

    def create_timestamps(
        self, 
        video_id: str, 
        timestamps: List[TimestampEstimate],
        frontend_mode: bool = False,
        job_id: Optional[str] = None
    ) -> bool:
        """
        Create timestamp records for a video.
        
        Args:
            video_id: Video ID
            timestamps: List of timestamp estimates
            frontend_mode: Whether called from frontend (enables SSE)
            job_id: Processing job ID for SSE updates
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not timestamps:
                logger.debug("No timestamps to save")
                return True
            
            logger.info(f"Creating {len(timestamps)} timestamps for video {video_id}")
            
            # Send SSE update if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.ANALYZING,
                    step="Saving timestamp analysis",
                    progress=80,
                    message=f"Saving {len(timestamps)} timestamps to database",
                    data={"timestamps_count": len(timestamps)},
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            # Prepare timestamp data
            timestamp_data = []
            for ts in timestamps:
                data = {
                    "video_id": video_id,
                    "time_from_seconds": ts.time_from_seconds,
                    "time_to_seconds": ts.time_to_seconds,
                    "statement": ts.statement,
                    "context": ts.context,
                    "category": ts.category.value if ts.category else None,
                    "confidence_score": ts.confidence_score
                }
                timestamp_data.append(data)
            
            response = self.supabase.table("video_timestamps").insert(timestamp_data).execute()
            
            if response.data:
                logger.info(f"Successfully created {len(response.data)} timestamps")
                
                # Send SSE update if in frontend mode
                if frontend_mode and job_id:
                    update = ProcessingUpdate(
                        job_id=job_id,
                        video_id=video_id,
                        status=ProcessingStatus.ANALYZING,
                        step="Timestamps saved successfully",
                        progress=85,
                        message=f"Successfully saved {len(response.data)} timestamps",
                        timestamp=datetime.utcnow()
                    )
                    asyncio.create_task(sse_service.broadcast_update(job_id, update))
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to create timestamps: {str(e)}")
            
            # Send SSE error if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.FAILED,
                    step="Timestamp saving failed",
                    progress=80,
                    message="Failed to save timestamps",
                    error=str(e),
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            return False

# Add missing import
import asyncio

# Create service instance
video_service = VideoService()