import os
from typing import List, Optional
from pathlib import Path
import logging
from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from pydantic import BaseModel
import asyncio
from typing import Optional
from datetime import datetime
from models.processing_models import ProcessingUpdate, ProcessingStatus
from services.sse_service import sse_service
import requests

load_dotenv()

logger = logging.getLogger(__name__)

class Word(BaseModel):
    text: str
    type: str
    logprob: float
    start: float
    end: float
    speaker_id: Optional[str] = None  

class TranscriptionResult(BaseModel):
    text: str
    model_id: str
    audio_file_path: str
    metadata: dict

class ElevenLabsTranscriptionService:
    def __init__(self):
        """Initialize ElevenLabs transcription service with API key from environment."""
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not found in environment variables")
        
        # Correct API URL for speech-to-text
        self.api_url = "https://api.elevenlabs.io/v1/speech-to-text"
        
        self.client = ElevenLabs(api_key=self.api_key)
        logger.info("ElevenLabs transcription service initialized successfully")
    
    def transcribe_audio(
        self, 
        audio_file_path: str, 
        model_id: str = "scribe_v1",
        frontend_mode: bool = False,
        job_id: Optional[str] = None,
        video_id: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio file using ElevenLabs Speech-to-Text API.
        
        Args:
            audio_file_path: Path to the audio file
            model_id: ElevenLabs model ID to use
            frontend_mode: Whether called from frontend (enables SSE)
            job_id: Processing job ID for SSE updates
            video_id: Video ID for SSE updates
            
        Returns:
            TranscriptionResult: Object containing transcription and metadata
            
        Raises:
            Exception: If transcription fails
        """
        try:
            logger.info(f"Starting transcription for audio file: {audio_file_path}")
            logger.info(f"Using model: {model_id}")
            
            # Send SSE update if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.TRANSCRIBING,
                    step="Initializing transcription",
                    progress=71,
                    message="Starting audio transcription with ElevenLabs",
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            # Check if file exists
            if not os.path.exists(audio_file_path):
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
            
            # Get file size for progress tracking
            file_size = os.path.getsize(audio_file_path)
            logger.info(f"Audio file size: {file_size / (1024*1024):.2f} MB")
            
            # Send SSE update for file upload start
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.TRANSCRIBING,
                    step="Uploading audio to ElevenLabs",
                    progress=75,
                    message=f"Uploading audio file ({file_size / (1024*1024):.1f} MB)",
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            # Correct file upload format for ElevenLabs API
            headers = {
                'xi-api-key': self.api_key
            }
            
            # Prepare files and data - FIXED FORMAT
            with open(audio_file_path, 'rb') as audio_file:
                files = {
                    'file': (os.path.basename(audio_file_path), audio_file, 'audio/mpeg')
                }
                
                # Data parameters as form data
                data = {
                    'model_id': model_id,
                    'language': 'en',  # Add language parameter
                    'response_format': 'json'  # Ensure JSON response
                }
                
                logger.debug("Sending transcription request to ElevenLabs API")
                logger.debug(f"Request headers: {headers}")
                logger.debug(f"Request data: {data}")
                
                # Send SSE update for API processing
                if frontend_mode and job_id:
                    update = ProcessingUpdate(
                        job_id=job_id,
                        video_id=video_id,
                        status=ProcessingStatus.TRANSCRIBING,
                        step="Processing with ElevenLabs AI",
                        progress=80,
                        message="ElevenLabs is processing the audio...",
                        timestamp=datetime.utcnow()
                    )
                    asyncio.create_task(sse_service.broadcast_update(job_id, update))
                
                # Make the API request with correct format
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=300  # 5 minute timeout
                )
            
            logger.debug(f"ElevenLabs API response status: {response.status_code}")
            logger.debug(f"ElevenLabs API response headers: {response.headers}")
            
            # Check if request was successful
            if not response.ok:
                error_detail = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"ElevenLabs API request failed: {error_detail}")
                
                # Try to parse error details
                try:
                    error_json = response.json()
                    if 'detail' in error_json:
                        error_detail = f"HTTP {response.status_code}: {error_json['detail']}"
                except:
                    pass
                
                raise Exception(f"ElevenLabs transcription failed: {error_detail}")
            
            # Send SSE update for successful API response
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.TRANSCRIBING,
                    step="Transcription completed",
                    progress=85,
                    message="Audio transcription completed successfully",
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            # Parse the response
            try:
                response_data = response.json()
                logger.debug(f"ElevenLabs API response received: {response_data}")
            except Exception as parse_error:
                logger.error(f"Failed to parse JSON response: {parse_error}")
                logger.error(f"Raw response: {response.text}")
                raise Exception(f"Invalid JSON response from ElevenLabs: {parse_error}")
            
            # Extract transcription text - handle different response formats
            transcription_text = ""
            if isinstance(response_data, dict):
                # Try different possible keys
                transcription_text = (
                    response_data.get('text') or 
                    response_data.get('transcription') or 
                    response_data.get('transcript') or
                    ""
                )
            elif isinstance(response_data, str):
                transcription_text = response_data
            
            if not transcription_text:
                logger.warning("Empty transcription received from ElevenLabs")
                logger.warning(f"Full response: {response_data}")
            
            # Create result object with correct structure
            result = TranscriptionResult(
                text=transcription_text,
                model_id=model_id,
                audio_file_path=audio_file_path,
                metadata=response_data if isinstance(response_data, dict) else {"raw_response": response_data}
            )
            
            logger.info("Audio transcription completed successfully")
            logger.info(f"Transcription length: {len(transcription_text)} characters")
            if transcription_text:
                logger.debug(f"Transcription preview: {transcription_text[:200]}...")
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to transcribe audio: {str(e)}"
            logger.error(error_msg)
            
            # Send SSE error if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.FAILED,
                    step="Transcription failed",
                    progress=75,
                    message="Audio transcription failed",
                    error=str(e),
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            raise Exception(error_msg)
    
    def cleanup_audio_file(self, audio_file_path: str):
        """Clean up a specific audio file."""
        try:
            if os.path.exists(audio_file_path):
                os.remove(audio_file_path)
                logger.info(f"Cleaned up audio file: {audio_file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup audio file {audio_file_path}: {str(e)}")
    
    def cleanup_all_audio_files(self, directory: str):
        """Clean up all audio files in a specific directory."""
        try:
            dir_path = Path(directory)
            if not dir_path.exists() or not dir_path.is_dir():
                logger.warning(f"Directory does not exist or is not a directory: {directory}")
                return
            
            for file in dir_path.glob("*.mp3"):
                try:
                    file.unlink()
                    logger.info(f"Cleaned up audio file: {file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup audio file {file}: {str(e)}")
        except Exception as e:
            logger.error(f"Error during cleanup of audio files: {str(e)}")

# Create service instance
transcription_service = ElevenLabsTranscriptionService()