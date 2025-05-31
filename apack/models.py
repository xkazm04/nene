from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


class StatementType(str, Enum):
    TRUTH = "Truth"
    SELECTIVE_TRUTH = "Selective Truth"
    LIE = "Lie"
    UNVERIFIABLE = "Unverifiable"


class ToneAnalysis(str, Enum):
    FACTUAL = "Factual"
    IRONIC = "Ironic"
    JOKING = "Joking"
    EMOTIONAL = "Emotional"
    AGGRESSIVE = "Aggressive"
    DEFENSIVE = "Defensive"


class Speaker(BaseModel):
    name: str
    role: Optional[str] = None
    party: Optional[str] = None


class EvaluationResult(BaseModel):
    statement_type: StatementType
    confidence_score: float = Field(ge=0.0, le=1.0)
    references: List[HttpUrl] = []
    llm_reasoning: str
    supporting_facts: List[str] = []
    contradicting_facts: List[str] = []


class Statement(BaseModel):
    start_time: float  # seconds
    end_time: float  # seconds
    speaker: Speaker
    text: str
    tone_analysis: Optional[ToneAnalysis] = None
    audio_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    evaluation: Optional[EvaluationResult] = None
    context: Optional[str] = None  # Additional context around the statement
    extended_evaluation: Optional[dict] = None  # Multi-agent evaluation data


class VideoProcessingRequest(BaseModel):
    video_path: str
    transcript_path: Optional[str] = None
    speakers: List[Speaker]
    enable_audio_analysis: bool = True
    enable_video_generation: bool = True
    output_video_duration: int = Field(default=30, description="Duration of output clips in seconds")


class FactCheckingResponse(BaseModel):
    request_id: str
    processed_at: datetime
    video_duration: float
    statements: List[Statement]
    summary: dict  # Overall statistics
    output_videos: Optional[List[str]] = None  # Paths to generated video clips