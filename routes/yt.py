from fastapi import APIRouter, HTTPException
import asyncio
from fastapi.responses import StreamingResponse
from typing import Dict, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl
import os

from models.processing_models import ProcessingUpdate, ProcessingStatus
from services.sse_service import sse_service
from services.media.yt_download import youtube_service
from services.media.eleven_transcription import transcription_service, TranscriptionResult
from services.pipelines.video_processing_pipeline import process_video_pipeline

import logging

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('video_processing.log')
    ]
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["youtube"])

class YouTubeTranscribeRequest(BaseModel):
    url: HttpUrl
    model_id: str = "scribe_v1"
    cleanup_audio: bool = True

class YouTubeTranscribeResponse(BaseModel):
    transcription: TranscriptionResult
    message: str
    audio_filepath: Optional[str] = None 

@router.post("/transcribe", response_model=YouTubeTranscribeResponse)
async def transcribe_youtube_video(request: YouTubeTranscribeRequest) -> YouTubeTranscribeResponse:
    """
    Download YouTube video, extract audio, and transcribe using ElevenLabs.
    
    Args:
        request: Request containing YouTube video URL and transcription options
        
    Returns:
        YouTubeTranscribeResponse: Contains transcription result
        
    Raises:
        HTTPException: If download or transcription fails
    """
    audio_filepath = None
    
    try:
        logger.info(f"🎬 Starting YouTube video transcription pipeline for URL: {request.url}")
        logger.info(f"📊 Transcription model: {request.model_id}")
        logger.info(f"🧹 Audio cleanup enabled: {request.cleanup_audio}")
        
        # Step 1: Download and extract audio
        logger.info("📥 Step 1: Downloading YouTube video and extracting audio")
        audio_filepath = youtube_service.download_audio(str(request.url))
        logger.info(f"✅ Audio successfully extracted to: {audio_filepath}")
        
        # Step 2: Transcribe audio using ElevenLabs
        logger.info("🎤 Step 2: Starting audio transcription with ElevenLabs")
        transcription_result = transcription_service.transcribe_audio(
            audio_file_path=audio_filepath,
            model_id=request.model_id,
        )
        logger.info("✅ Audio transcription completed successfully")
        
        # Step 3: Cleanup audio file if requested
        if request.cleanup_audio:
            logger.info("🧹 Step 3: Cleaning up temporary audio file")
            transcription_service.cleanup_audio_file(audio_filepath)
            audio_filepath = None  
        else:
            logger.info("⏭️ Step 3: Skipping audio cleanup as requested")
        
        logger.info("🎉 YouTube video transcription pipeline completed successfully")
        logger.info(f"📄 Final transcription preview: {transcription_result.text[:100]}...")
        
        return YouTubeTranscribeResponse(
            transcription=transcription_result,
            message="Video successfully downloaded and transcribed",
            audio_filepath=audio_filepath
        )
        
    except Exception as e:
        error_msg = f"Failed to transcribe YouTube video: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"🔍 Error type: {type(e).__name__}")
        
        # Cleanup audio file on error if it exists
        if audio_filepath:
            try:
                transcription_service.cleanup_audio_file(audio_filepath)
                logger.info("🧹 Cleaned up audio file after error")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Failed to cleanup audio file after error: {cleanup_error}")
        
        raise HTTPException(status_code=400, detail=error_msg)

@router.post("/download-audio", response_model=Dict[str, str])
async def download_youtube_audio(request: YouTubeTranscribeRequest) -> Dict[str, str]:
    """
    Download YouTube video and extract audio to temporary file (legacy endpoint).
    
    Args:
        request: Request containing YouTube video URL
        
    Returns:
        Dict containing audio filepath and message
        
    Raises:
        HTTPException: If download fails
    """
    try:
        logger.info(f"📥 Starting YouTube audio download for URL: {request.url}")
        
        # Download and extract audio
        audio_filepath = youtube_service.download_audio(str(request.url))
        
        logger.info(f"✅ Successfully downloaded audio to: {audio_filepath}")
        
        return {
            "audio_filepath": audio_filepath,
            "message": "Audio successfully downloaded and extracted"
        }
        
    except Exception as e:
        error_msg = f"Failed to download YouTube audio: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

@router.post("/cleanup")
async def cleanup_temp_files(older_than_hours: int = 24) -> Dict[str, str]:
    """
    Clean up temporary audio files older than specified hours.
    
    Args:
        older_than_hours: Remove files older than this many hours (default: 24)
        
    Returns:
        Dict with cleanup status message
    """
    try:
        logger.info(f"🧹 Starting cleanup of temporary files older than {older_than_hours} hours")
        youtube_service.cleanup_temp_files(older_than_hours)
        logger.info("✅ Temporary files cleanup completed successfully")
        return {"message": f"Cleaned up temporary files older than {older_than_hours} hours"}
    except Exception as e:
        logger.error(f"❌ Failed to cleanup temp files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for YouTube download service."""
    logger.info("💓 Health check requested")
    return {"status": "healthy", "service": "youtube-transcription"}

class VideoProcessingRequest(BaseModel):
    url: HttpUrl
    speaker_name: Optional[str] = None
    context: Optional[str] = "Political speech or interview"
    language_code: str = "en"
    model_id: str = "scribe_v1"
    cleanup_audio: bool = True
    research_statements: bool = True

class VideoProcessingResponse(BaseModel):
    job_id: str
    stream_url: str
    message: str

# def get_base_url() -> str:
#     """Get the base URL for the API."""
#     # Try to get from environment variable first
#     base_url = os.getenv("API_BASE_URL")
#     if base_url:
#         return base_url.rstrip('/')
    
#     # Fallback to default for development
#     return "http://localhost:8080"

# @router.post("/process-video", response_model=VideoProcessingResponse)
# async def start_video_processing(request: VideoProcessingRequest) -> VideoProcessingResponse:
#     """
#     Start complete video processing pipeline with real-time SSE updates.
    
#     Args:
#         request: Video processing request with URL and options
        
#     Returns:
#         VideoProcessingResponse: Job ID and stream URL for real-time updates
#     """
#     try:
#         logger.info("=" * 60)
#         logger.info(f"🚀 STARTING VIDEO PROCESSING REQUEST")
#         logger.info(f"   URL: {request.url}")
#         logger.info(f"   Speaker: {request.speaker_name}")
#         logger.info(f"   Context: {request.context}")
#         logger.info(f"   Language: {request.language_code}")
#         logger.info(f"   Model: {request.model_id}")
#         logger.info(f"   Cleanup: {request.cleanup_audio}")
#         logger.info(f"   Research: {request.research_statements}")
#         logger.info("=" * 60)
        
#         # Create processing job
#         job_id = sse_service.create_job(str(request.url))
#         logger.info(f"📋 Created processing job: {job_id}")
        
#         # Start background processing
#         task = asyncio.create_task(
#             process_video_pipeline(
#                 job_id=job_id,
#                 video_url=str(request.url),
#                 speaker_name=request.speaker_name,
#                 context=request.context,
#                 language_code=request.language_code,
#                 model_id=request.model_id,
#                 cleanup_audio=request.cleanup_audio,
#                 research_statements=request.research_statements
#             )
#         )
        
#         logger.info(f"🔄 Background processing task started for job {job_id}")
        
#         # Construct full stream URL
#         base_url = get_base_url()
#         stream_url = f"{base_url}/yt/stream/{job_id}"
#         logger.info(f"📡 Stream URL: {stream_url}")
        
#         return VideoProcessingResponse(
#             job_id=job_id,
#             stream_url=stream_url,
#             message="Video processing started. Connect to stream_url for real-time updates."
#         )
        
#     except Exception as e:
#         error_msg = f"Failed to start video processing: {str(e)}"
#         logger.error(f"❌ {error_msg}")
#         logger.error(f"🔍 Error type: {type(e).__name__}")
#         raise HTTPException(status_code=400, detail=error_msg)

@router.get("/stream/{job_id}")
async def stream_processing_updates(job_id: str):
    """
    Stream real-time processing updates via Server-Sent Events.
    
    Args:
        job_id: Processing job ID
        
    Returns:
        StreamingResponse: SSE stream of processing updates
    """
    try:
        logger.info(f"📡 Starting SSE stream for job {job_id}")
        
        # Check if job exists
        job = sse_service.get_job(job_id)
        if not job:
            logger.error(f"❌ Processing job not found: {job_id}")
            raise HTTPException(status_code=404, detail="Processing job not found")
        
        logger.info(f"✅ Job found, establishing SSE connection for {job_id}")
        
        return StreamingResponse(
            sse_service.add_connection(job_id),
            media_type="text/event-stream", 
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to start SSE stream for {job_id}: {str(e)}")
        logger.error(f"🔍 Error type: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=f"Stream failed: {str(e)}")