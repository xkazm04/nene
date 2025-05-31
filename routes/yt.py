from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Dict, Optional # Import Optional
import logging
from services.yt_download import youtube_service
from services.eleven_transcription import transcription_service, TranscriptionResult

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["youtube"])

class YouTubeTranscribeRequest(BaseModel):
    url: HttpUrl
    model_id: str = "scribe_v1"
    cleanup_audio: bool = True

class YouTubeTranscribeResponse(BaseModel):
    transcription: TranscriptionResult
    message: str
    audio_filepath: Optional[str] = None # Allow None as a valid value

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
        logger.info(f"Starting YouTube video transcription pipeline for URL: {request.url}")
        logger.info(f"Transcription model: {request.model_id}")
        logger.info(f"Audio cleanup enabled: {request.cleanup_audio}")
        
        # Step 1: Download and extract audio
        logger.info("Step 1: Downloading YouTube video and extracting audio")
        audio_filepath = youtube_service.download_audio(str(request.url))
        logger.info(f"Audio successfully extracted to: {audio_filepath}")
        
        # Step 2: Transcribe audio using ElevenLabs
        logger.info("Step 2: Starting audio transcription with ElevenLabs")
        transcription_result = transcription_service.transcribe_audio(
            audio_file_path=audio_filepath,
            model_id=request.model_id,
        )
        logger.info("Audio transcription completed successfully")
        
        # Step 3: Cleanup audio file if requested
        if request.cleanup_audio:
            logger.info("Step 3: Cleaning up temporary audio file")
            transcription_service.cleanup_audio_file(audio_filepath)
            audio_filepath = None  
        else:
            logger.info("Step 3: Skipping audio cleanup as requested")
        
        logger.info("YouTube video transcription pipeline completed successfully")
        logger.info(f"Final transcription preview: {transcription_result.text[:100]}...")
        
        return YouTubeTranscribeResponse(
            transcription=transcription_result,
            message="Video successfully downloaded and transcribed",
            audio_filepath=audio_filepath
        )
        
    except Exception as e:
        error_msg = f"Failed to transcribe YouTube video: {str(e)}"
        logger.error(error_msg)
        
        # Cleanup audio file on error if it exists
        if audio_filepath:
            try:
                transcription_service.cleanup_audio_file(audio_filepath)
                logger.info("Cleaned up audio file after error")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup audio file after error: {cleanup_error}")
        
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
        logger.info(f"Starting YouTube audio download for URL: {request.url}")
        
        # Download and extract audio
        audio_filepath = youtube_service.download_audio(str(request.url))
        
        logger.info(f"Successfully downloaded audio to: {audio_filepath}")
        
        return {
            "audio_filepath": audio_filepath,
            "message": "Audio successfully downloaded and extracted"
        }
        
    except Exception as e:
        error_msg = f"Failed to download YouTube audio: {str(e)}"
        logger.error(error_msg)
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
        logger.info(f"Starting cleanup of temporary files older than {older_than_hours} hours")
        youtube_service.cleanup_temp_files(older_than_hours)
        logger.info("Temporary files cleanup completed successfully")
        return {"message": f"Cleaned up temporary files older than {older_than_hours} hours"}
    except Exception as e:
        logger.error(f"Failed to cleanup temp files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for YouTube download service."""
    return {"status": "healthy", "service": "youtube-transcription"}