from typing import List, Optional
from pydantic import BaseModel
from models.research_models import StatementCategory
from models.video_models import EnhancedFactCheckStatementWithTimestamp

class TranscriptionAnalysisInput(BaseModel):
    language_code: str = "eng"
    speaker: str
    context: str
    transcription: str
    video_duration_seconds: Optional[int] = None  

class EnhancedFactCheckStatement(BaseModel):
    statement: str
    language: Optional[str] = None  
    context: Optional[str] = None   
    category: Optional[StatementCategory] = None

class EnhancedTranscriptionAnalysisResult(BaseModel):
    statements: List[EnhancedFactCheckStatementWithTimestamp]  
    total_statements: int
    analysis_summary: str
    overall_context: Optional[str] = None 
    detected_language: Optional[str] = None  
    dominant_categories: Optional[List[StatementCategory]] = None  
    estimated_duration: Optional[int] = None  