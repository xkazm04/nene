from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional
from services.llm_research import (
    ExpertOpinion,
    ResourceAnalysis  
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

class EnhancedLLMResearchResponse(BaseModel):
    request: ResearchRequestAPI
    valid_sources: str
    verdict: str
    status: str
    correction: Optional[str] = None
    resources_agreed: ResourceAnalysis  
    resources_disagreed: ResourceAnalysis  
    experts: ExpertOpinion
    processed_at: datetime
    database_id: Optional[str] = None
    is_duplicate: bool = False  
    
    
# DB - service
class ResearchRequest(BaseModel):
    statement: str
    source: str
    context: str
    datetime: datetime
    statement_date: Optional[date] = None  # New field for when the statement was made

