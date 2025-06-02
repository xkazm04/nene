from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional
from models.research_models import (
    ExpertOpinion,
    ResourceAnalysis,
    StatementCategory
)

# llm - route
class AnalysisRequest(BaseModel):
    language_code: str = "eng"
    speaker: str
    context: str
    transcription: str

class ResearchRequestAPI(BaseModel):
    statement: str
    source: str = "Unknown"
    context: str = ""
    datetime: datetime
    statement_date: Optional[date] = None
    country: Optional[str] = None  # ISO country code (e.g., "us", "gb", "de")
    category: Optional[StatementCategory] = None  

class EnhancedLLMResearchResponse(BaseModel):
    request: ResearchRequestAPI
    valid_sources: str
    verdict: str
    status: str
    correction: Optional[str] = None
    country: Optional[str] = None  # ISO country code
    category: Optional[StatementCategory] = None  
    resources_disagreed: Optional[ResourceAnalysis] = None  
    experts: Optional[ExpertOpinion] = None
    processed_at: datetime
    database_id: Optional[str] = None
    is_duplicate: bool = False
    
# DB - service
class ResearchRequest(BaseModel):
    statement: str
    source: str
    context: str
    datetime: datetime
    statement_date: Optional[date] = None
    country: Optional[str] = None  # ISO country code
    category: Optional[str] = None
