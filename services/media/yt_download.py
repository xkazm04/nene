import os
import tempfile
import asyncio
from pathlib import Path
import yt_dlp
import logging
from datetime import datetime
from typing import Optional
from services.media.video_service import video_service
from models.processing_models import ProcessingUpdate, ProcessingStatus
from services.sse_service import sse_service

logger = logging.getLogger(__name__)

class YouTubeDownloadService:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "yt_downloads"
        self.temp_dir.mkdir(exist_ok=True)
        logger.info(f"YouTube download service initialized. Temp dir: {self.temp_dir}")
    
    def download_audio(
        self, 
        youtube_url: str, 
        speaker_name: str = None,
        frontend_mode: bool = False,
        job_id: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Download YouTube video and extract audio to temporary file.
        
        Args:
            youtube_url: YouTube video URL
            speaker_name: Optional speaker name for metadata
            frontend_mode: Whether called from frontend (enables SSE)
            job_id: Processing job ID for SSE updates
            
        Returns:
            tuple: (audio_file_path, video_id) - Path to the extracted audio file and database video ID
            
        Raises:
            Exception: If download or extraction fails
        """
        video_info = None
        audio_path = None
        
        try:
            logger.info(f"Starting audio download for: {youtube_url}")
            
            # Send SSE update if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    status=ProcessingStatus.DOWNLOADING,
                    step="Initializing YouTube download",
                    progress=5,
                    message="Starting YouTube video download",
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            # Configure yt-dlp options for audio extraction with better error handling
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(self.temp_dir / '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'postprocessor_args': [
                    '-ar', '16000'  # Set sample rate to 16kHz for better compatibility
                ],
                'keepvideo': False,  # Don't keep original video file
                'extract_flat': False,
                'writethumbnail': False,
                'writeinfojson': False,
                'no_warnings': False,  # Enable warnings for debugging
                'ignoreerrors': False,  # Don't ignore errors
            }
            
            # Send SSE update for metadata extraction
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    status=ProcessingStatus.DOWNLOADING,
                    step="Extracting video metadata",
                    progress=10,
                    message="Extracting video information",
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # Extract info to get video metadata
                    logger.info("Extracting video metadata...")
                    info = ydl.extract_info(youtube_url, download=False)
                    
                    if not info:
                        raise Exception("Failed to extract video information")
                    
                    video_info = {
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration'),  # Duration in seconds
                        'uploader': info.get('uploader'),
                        'upload_date': info.get('upload_date')
                    }
                    
                    title = info.get('title', 'audio')
                    logger.info(f"Video metadata extracted. Title: {title}, Duration: {video_info.get('duration')}s")
                    
                    # Send SSE update with video info
                    if frontend_mode and job_id:
                        update = ProcessingUpdate(
                            job_id=job_id,
                            status=ProcessingStatus.DOWNLOADING,
                            step="Video metadata extracted",
                            progress=20,
                            message=f"Found video: {title}",
                            data={
                                "title": title,
                                "duration": video_info.get('duration'),
                                "uploader": video_info.get('uploader')
                            },
                            timestamp=datetime.utcnow()
                        )
                        asyncio.create_task(sse_service.broadcast_update(job_id, update))
                    
                except Exception as extract_error:
                    logger.error(f"Failed to extract video metadata: {str(extract_error)}")
                    raise Exception(f"Failed to extract video information: {str(extract_error)}")
                
                # Clean filename for filesystem compatibility
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title[:100]  # Limit length to avoid filesystem issues
                
                if not safe_title:
                    safe_title = "audio_file"
                
                audio_filename = f"{safe_title}.mp3"
                expected_audio_path = self.temp_dir / audio_filename
                
                # Update output template with cleaned filename
                ydl_opts['outtmpl'] = str(self.temp_dir / f"{safe_title}.%(ext)s")
                
                # Send SSE update for download start
                if frontend_mode and job_id:
                    update = ProcessingUpdate(
                        job_id=job_id,
                        status=ProcessingStatus.DOWNLOADING,
                        step="Downloading and extracting audio",
                        progress=30,
                        message="Downloading video and extracting audio...",
                        timestamp=datetime.utcnow()
                    )
                    asyncio.create_task(sse_service.broadcast_update(job_id, update))
                
                # Download and extract audio
                logger.info("Starting video download and audio extraction...")
                
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                        ydl_download.download([youtube_url])
                        logger.info("Download completed successfully")
                        
                except Exception as download_error:
                    logger.error(f"Download failed: {str(download_error)}")
                    raise Exception(f"Failed to download video: {str(download_error)}")
                
                # Find the audio file
                logger.info(f"Looking for audio file. Expected path: {expected_audio_path}")
                
                final_audio_path = None
                
                if expected_audio_path.exists():
                    final_audio_path = str(expected_audio_path)
                    logger.info(f"Found expected audio file: {final_audio_path}")
                else:
                    # Fallback: find the most recently created mp3 file
                    logger.warning(f"Expected audio file not found at {expected_audio_path}")
                    logger.info("Searching for any MP3 files in temp directory...")
                    
                    mp3_files = list(self.temp_dir.glob("*.mp3"))
                    logger.info(f"Found {len(mp3_files)} MP3 files: {[str(f) for f in mp3_files]}")
                    
                    if mp3_files:
                        latest_file = max(mp3_files, key=os.path.getctime)
                        final_audio_path = str(latest_file)
                        logger.info(f"Using most recent MP3 file: {final_audio_path}")
                    else:
                        # Check for other audio formats
                        audio_files = []
                        for ext in ['*.m4a', '*.wav', '*.webm']:
                            audio_files.extend(list(self.temp_dir.glob(ext)))
                        
                        logger.info(f"Found {len(audio_files)} other audio files: {[str(f) for f in audio_files]}")
                        
                        if audio_files:
                            latest_file = max(audio_files, key=os.path.getctime)
                            final_audio_path = str(latest_file)
                            logger.warning(f"Using non-MP3 audio file: {final_audio_path}")
                        else:
                            # List all files in temp directory for debugging
                            all_files = list(self.temp_dir.glob("*"))
                            logger.error(f"No audio files found. All files in temp dir: {[str(f) for f in all_files]}")
                            raise Exception("Audio file not found after download")
                
                if not final_audio_path or not os.path.exists(final_audio_path):
                    raise Exception(f"Audio file not accessible: {final_audio_path}")
                
                # Verify file is not empty
                file_size = os.path.getsize(final_audio_path)
                if file_size == 0:
                    raise Exception("Downloaded audio file is empty")
                
                logger.info(f"Audio file ready: {final_audio_path} ({file_size / (1024*1024):.2f} MB)")
            
            # Send SSE update for download completion
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    status=ProcessingStatus.DOWNLOADING,
                    step="Audio extraction completed",
                    progress=60,
                    message="Audio successfully extracted",
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            # Create video record in database
            video_id = self._create_video_record(
                youtube_url, 
                video_info, 
                speaker_name,
                frontend_mode=frontend_mode,
                job_id=job_id
            )
            
            logger.info(f"Audio download completed successfully. Video ID: {video_id}")
            
            # Send final SSE update for this phase
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.DOWNLOADING,
                    step="Download phase completed",
                    progress=70,
                    message="Video download and audio extraction completed successfully",
                    data={"audio_path": final_audio_path},
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            return final_audio_path, video_id
                        
        except Exception as e:
            logger.error(f"Failed to download YouTube audio: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            
            # Send SSE error if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    status=ProcessingStatus.FAILED,
                    step="Download failed",
                    progress=0,
                    message="Failed to download YouTube audio",
                    error=str(e),
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            raise Exception(f"Failed to download YouTube audio: {str(e)}")
    
    def _create_video_record(
        self, 
        video_url: str, 
        video_info: dict, 
        speaker_name: str = None,
        frontend_mode: bool = False,
        job_id: Optional[str] = None
    ) -> str:
        """
        Create video record in database with metadata.
        
        Args:
            video_url: YouTube URL
            video_info: Video metadata from yt-dlp
            speaker_name: Optional speaker name
            frontend_mode: Whether called from frontend (enables SSE)
            job_id: Processing job ID for SSE updates
            
        Returns:
            str: Video database ID
        """
        try:
            logger.info("Creating video record in database...")
            
            video_data = {
                "source": "youtube",
                "title": video_info.get('title'),
                "duration_seconds": video_info.get('duration'),
                "speaker_name": speaker_name,
                "audio_extracted": True  # Mark as extracted since we just did it
            }
            
            video_id = video_service.create_video_record(
                video_url, 
                frontend_mode=frontend_mode,
                job_id=job_id,
                **video_data
            )
            
            if not video_id:
                raise Exception("Failed to create video record in database")
            
            logger.info(f"Created video record with ID: {video_id}")
            return video_id
            
        except Exception as e:
            logger.error(f"Failed to create video record: {str(e)}")
            raise Exception(f"Failed to create video record: {str(e)}")
    
    def cleanup_temp_files(self, older_than_hours: int = 24):
        """Clean up temporary files older than specified hours."""
        import time
        try:
            current_time = time.time()
            cutoff_time = current_time - (older_than_hours * 3600)
            
            cleaned_count = 0
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        logger.debug(f"Cleaned up temp file: {file_path}")
                        cleaned_count += 1
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup {file_path}: {cleanup_error}")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old temporary files")
                
        except Exception as e:
            logger.error(f"Error during temp file cleanup: {str(e)}")

# Create service instance
youtube_service = YouTubeDownloadService()