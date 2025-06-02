from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel
from enum import Enum

class ProcessingStatus(str, Enum):
    """Processing job status enumeration."""
    CREATED = "created"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    RESEARCHING = "researching"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessingStep(str, Enum):
    """Processing step enumeration."""
    DOWNLOAD_AUDIO = "download_audio"
    TRANSCRIBE_AUDIO = "transcribe_audio"
    ANALYZE_TRANSCRIPTION = "analyze_transcription"
    RESEARCH_STATEMENT = "research_statement"
    COMPLETE = "complete"

class ProcessingUpdate(BaseModel):
    """Model for SSE progress updates."""
    type: str = "progress"
    job_id: str
    video_id: Optional[str] = None
    status: ProcessingStatus
    step: str
    progress: int  # 0-100
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime
    error: Optional[str] = None

class ProcessingJob(BaseModel):
    """Model for processing job record."""
    id: Optional[str] = None
    video_id: Optional[str] = None
    video_url: str
    status: ProcessingStatus = ProcessingStatus.CREATED
    current_step: Optional[str] = None
    progress_percentage: int = 0
    statements_total: int = 0
    statements_completed: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class StatementResearchProgress(BaseModel):
    """Model for individual statement research progress."""
    statement: str
    category: Optional[str] = None
    status: str  # 'pending', 'researching', 'completed', 'failed'
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None