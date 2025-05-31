import os
from typing import List, Optional
from pathlib import Path
import logging
from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class Word(BaseModel):
    text: str
    type: str
    logprob: float
    start: float
    end: float
    speaker_id: Optional[str] = None  # Make speaker_id optional since it can be None

class TranscriptionResult(BaseModel):
    language_code: str
    language_probability: float
    text: str
    words: List[Word]

class ElevenLabsTranscriptionService:
    def __init__(self):
        """Initialize ElevenLabs transcription service with API key from environment."""
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not found in environment variables")
        
        self.client = ElevenLabs(api_key=self.api_key)
        logger.info("ElevenLabs transcription service initialized successfully")
    
    def transcribe_audio(self, audio_file_path: str, model_id: str = "scribe_v1") -> TranscriptionResult:
        """
        Transcribe audio file using ElevenLabs Speech-to-Text API.
        
        Args:
            audio_file_path: Path to the audio file to transcribe
            model_id: ElevenLabs model ID for transcription (default: scribe_v1)
            
        Returns:
            TranscriptionResult: Transcription result with text and word-level details
            
        Raises:
            Exception: If transcription fails
        """
        try:
            audio_path = Path(audio_file_path)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
            
            logger.info(f"Starting transcription for audio file: {audio_file_path}")
            logger.info(f"Using model: {model_id}")
            logger.info(f"Audio file size: {audio_path.stat().st_size / (1024*1024):.2f} MB")
            
            # Open and read the audio file
            with open(audio_file_path, "rb") as audio_file:
                logger.debug("Sending audio file to ElevenLabs API")
                
                # Call ElevenLabs Speech-to-Text API with correct parameter name
                response = self.client.speech_to_text.convert(
                    model_id=model_id,
                    file=audio_file,
                    enable_logging=True,
                    timestamps_granularity="none",
                )
                
                logger.info("Successfully received transcription response from ElevenLabs")
                logger.info(f"Detected language: {response.language_code} (confidence: {response.language_probability:.2f})")
                logger.info(f"Transcribed text length: {len(response.text)} characters")
                logger.info(f"Number of words: {len(response.words)}")
                
                # Convert response to our Pydantic model with safe handling of None values
                words = []
                for word in response.words:
                    try:
                        word_obj = Word(
                            text=word.text,
                            type=word.type,
                            logprob=word.logprob,
                            start=word.start,
                            end=word.end,
                            speaker_id=word.speaker_id if hasattr(word, 'speaker_id') and word.speaker_id is not None else None
                        )
                        words.append(word_obj)
                    except Exception as word_error:
                        logger.warning(f"Failed to parse word: {word_error}. Skipping word: {getattr(word, 'text', 'unknown')}")
                        continue
                
                result = TranscriptionResult(
                    language_code=response.language_code,
                    language_probability=response.language_probability,
                    text=response.text,
                    words=words
                )
                
                logger.info("Transcription completed successfully")
                logger.info(f"Successfully parsed {len(words)} words")
                logger.debug(f"Transcription preview: {response.text[:200]}...")
                
                return result
                
        except FileNotFoundError as e:
            error_msg = f"Audio file not found: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to transcribe audio with ElevenLabs: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            raise Exception(error_msg)
    
    def cleanup_audio_file(self, audio_file_path: str) -> None:
        """
        Clean up the audio file after transcription.
        
        Args:
            audio_file_path: Path to the audio file to delete
        """
        try:
            audio_path = Path(audio_file_path)
            if audio_path.exists():
                file_size = audio_path.stat().st_size / (1024*1024)
                audio_path.unlink()
                logger.info(f"Cleaned up audio file: {audio_file_path} ({file_size:.2f} MB)")
            else:
                logger.warning(f"Audio file not found during cleanup: {audio_file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup audio file {audio_file_path}: {str(e)}")

# Create service instance
transcription_service = ElevenLabsTranscriptionService()