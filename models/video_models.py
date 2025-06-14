from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from models.research_models import StatementCategory

class VideoTimestamp(BaseModel):
    """Model for video timestamp with statement."""
    id: Optional[str] = None
    video_id: str
    research_id: Optional[str] = None
    time_from_seconds: int
    time_to_seconds: int
    statement: str
    context: Optional[str] = None
    category: Optional[StatementCategory] = None
    confidence_score: Optional[float] = None
    created_at: Optional[datetime] = None

class ResearchResult(BaseModel):
    """Model for research result data."""
    id: Optional[str] = None
    source: Optional[str] = None
    country: Optional[str] = None
    valid_sources: Optional[str] = None
    verdict: Optional[str] = None
    status: Optional[str] = None
    correction: Optional[str] = None
    resources_agreed: Optional[Dict[str, Any]] = None
    resources_disagreed: Optional[Dict[str, Any]] = None
    experts: Optional[Dict[str, Any]] = None
    processed_at: Optional[datetime] = None

class TimestampWithResearch(BaseModel):
    """Combined model for timestamp with optional research data."""
    # Timestamp data
    time_from_seconds: int
    time_to_seconds: int
    statement: str
    context: Optional[str] = None
    category: Optional[StatementCategory] = None
    confidence_score: Optional[float] = None
    
    # Research data (all optional - only present if research was completed)
    research: Optional[ResearchResult] = None

class Video(BaseModel):
    """Model for video record."""
    id: Optional[str] = None
    video_url: str
    source: str  # 'youtube', 'tiktok', etc.
    researched: bool = False
    title: Optional[str] = None
    verdict: Optional[str] = None
    duration_seconds: Optional[int] = None
    speaker_name: Optional[str] = None
    language_code: Optional[str] = None
    audio_extracted: bool = False
    transcribed: bool = False
    analyzed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

class VideoDetailResponse(BaseModel):
    """Complete video detail response with timestamps and research."""
    # Video base data
    video_url: str
    source: str
    title: Optional[str] = None
    verdict: Optional[str] = None
    duration_seconds: Optional[int] = None
    speaker_name: Optional[str] = None
    language_code: Optional[str] = None
    processed_at: Optional[datetime] = None
    
    # Combined timestamps with research data
    timestamps: List[TimestampWithResearch] = []
    
    # Summary statistics
    total_statements: int = 0
    researched_statements: int = 0
    research_completion_rate: float = 0.0

# Legacy models for backwards compatibility
class VideoWithTimestamps(BaseModel):
    """Model for video with all its timestamps."""
    video: Video
    timestamps: List[VideoTimestamp]

class TimestampEstimate(BaseModel):
    """Model for timestamp estimation from transcription."""
    statement: str
    time_from_seconds: int
    time_to_seconds: int
    context: Optional[str] = None
    category: Optional[StatementCategory] = None
    confidence_score: Optional[float] = None

class EnhancedFactCheckStatementWithTimestamp(BaseModel):
    """Enhanced fact-check statement with timestamp information."""
    statement: str
    language: Optional[str] = None
    context: Optional[str] = None
    category: Optional[StatementCategory] = None
    # New timestamp fields
    estimated_time_from: Optional[int] = None  # Seconds from start
    estimated_time_to: Optional[int] = None    # Seconds from start
    confidence_score: Optional[float] = None   # 0.0-1.0 confidence in timing