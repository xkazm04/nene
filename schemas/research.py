from pydantic import BaseModel, validator
from datetime import datetime, date
from typing import Optional, Literal, List, Union, Dict, Any
from models.research_models import (
    ExpertOpinion,
    ResourceAnalysis,
    StatementCategory,
    ExpertPerspective,
    ResearchMetadata
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
    # Core LLM response fields
    valid_sources: str
    verdict: str
    status: Literal["TRUE", "FACTUAL_ERROR", "DECEPTIVE_LIE", "MANIPULATIVE", "PARTIALLY_TRUE", "OUT_OF_CONTEXT", "UNVERIFIABLE"]
    correction: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    resources_agreed: Optional[Union[Dict[str, Any], ResourceAnalysis]] = None
    resources_disagreed: Optional[Union[Dict[str, Any], ResourceAnalysis]] = None
    experts: Optional[Union[Dict[str, Any], ExpertOpinion]] = None
    research_method: str
    profile_id: Optional[str] = None
    
    # Enhanced tri-factor fields
    expert_perspectives: List[Union[Dict[str, Any], ExpertPerspective]] = []
    key_findings: List[str] = []
    research_summary: str = ""
    confidence_score: int = 50
    research_metadata: Optional[Union[Dict[str, Any], ResearchMetadata, str]] = None  # Allow string for simple metadata
    llm_findings: List[str] = []
    web_findings: List[str] = []
    resource_findings: List[str] = []
    
    # Request metadata
    request_statement: str
    request_source: str
    request_context: str
    request_datetime: Union[str, datetime]
    request_country: Optional[str] = None
    request_category: Optional[str] = None
    processed_at: Union[str, datetime]
    
    # Database and processing metadata
    database_id: Optional[str] = None
    is_duplicate: bool = False
    
    # Error handling metadata
    research_errors: List[str] = []
    fallback_reason: Optional[str] = None
    
    class Config:
        # Allow both dict and model instances
        arbitrary_types_allowed = True
        
    @validator('request_datetime', 'processed_at', pre=True)
    def convert_datetime_to_string(cls, v):
        """Convert datetime objects to ISO format strings"""
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    @validator('resources_agreed', 'resources_disagreed', 'experts', pre=True)
    def convert_models_to_dict(cls, v):
        """Convert Pydantic models to dictionaries for JSON serialization"""
        if hasattr(v, 'model_dump'):
            return v.model_dump()
        elif hasattr(v, 'dict'):
            return v.dict()
        return v
    
    @validator('research_metadata', pre=True)
    def convert_research_metadata(cls, v):
        """Convert ResearchMetadata to dict or keep as string"""
        if isinstance(v, str):
            return v  # Keep string as-is
        elif hasattr(v, 'model_dump'):
            return v.model_dump()
        elif hasattr(v, 'dict'):
            return v.dict()
        return v
    
    @validator('expert_perspectives', pre=True)
    def convert_expert_perspectives_to_dict(cls, v):
        """Convert list of ExpertPerspective models to dictionaries"""
        if not v:
            return []
        
        result = []
        for item in v:
            if hasattr(item, 'model_dump'):
                result.append(item.model_dump())
            elif hasattr(item, 'dict'):
                result.append(item.dict())
            else:
                result.append(item)
        return result

# DB - service
class ResearchRequest(BaseModel):
    statement: str
    source: str
    context: str
    datetime: datetime
    statement_date: Optional[date] = None
    country: Optional[str] = None  # ISO country code
    category: Optional[str] = None
    profile_id: Optional[str] = None