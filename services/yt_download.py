import os
import tempfile
from pathlib import Path
import yt_dlp

class YouTubeDownloadService:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "yt_downloads"
        self.temp_dir.mkdir(exist_ok=True)
    
    def download_audio(self, youtube_url: str) -> str:
        """
        Download YouTube video and extract audio to temporary file.
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            str: Path to the extracted audio file
            
        Raises:
            Exception: If download or extraction fails
        """
        try:
            # Configure yt-dlp options for audio extraction
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
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info to get the filename
                info = ydl.extract_info(youtube_url, download=False)
                title = info.get('title', 'audio')
                
                # Clean filename for filesystem compatibility
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                audio_filename = f"{safe_title}.mp3"
                audio_path = self.temp_dir / audio_filename
                
                # Update output template with cleaned filename
                ydl_opts['outtmpl'] = str(self.temp_dir / f"{safe_title}.%(ext)s")
                
                # Download and extract audio
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                    ydl_download.download([youtube_url])
                
                # Return the path to the audio file
                if audio_path.exists():
                    return str(audio_path)
                else:
                    # Fallback: find the most recently created mp3 file
                    mp3_files = list(self.temp_dir.glob("*.mp3"))
                    if mp3_files:
                        latest_file = max(mp3_files, key=os.path.getctime)
                        return str(latest_file)
                    else:
                        raise Exception("Audio file not found after download")
                        
        except Exception as e:
            raise Exception(f"Failed to download YouTube audio: {str(e)}")
    
    def cleanup_temp_files(self, older_than_hours: int = 24):
        """
        Clean up temporary files older than specified hours.
        
        Args:
            older_than_hours: Remove files older than this many hours
        """
        import time
        current_time = time.time()
        cutoff_time = current_time - (older_than_hours * 3600)
        
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                except Exception:
                    pass  # Ignore errors when deleting temp files

# Create service instance
youtube_service = YouTubeDownloadService()