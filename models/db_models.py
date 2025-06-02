from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from models.research_models import ExpertOpinion, ResourceAnalysis

class ResearchResultDB(BaseModel):
    """Database model for research results."""
    id: Optional[str] = None
    statement: str
    source: Optional[str] = None
    context: Optional[str] = None
    request_datetime: str
    statement_date: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    profile_id: Optional[str] = None
    valid_sources: str
    verdict: str
    status: str
    correction: Optional[str] = None
    resources_agreed: Optional[Dict[str, Any]] = None
    resources_disagreed: Optional[Dict[str, Any]] = None
    experts: Optional[Dict[str, Any]] = None
    processed_at: str

class ResearchResourceDB(BaseModel):
    """Database model for research resources."""
    research_result_id: str
    url: str
    order_index: int

class SearchFilters(BaseModel):
    """Search filters for research results."""
    search_text: Optional[str] = None
    status_filter: Optional[str] = None
    country_filter: Optional[str] = None
    category_filter: Optional[str] = None
    profile_filter: Optional[str] = None
    limit: int = 50
    offset: int = 0

class AnalyticsSummary(BaseModel):
    """Analytics summary for research results."""
    total_statements: int
    recent_activity: int
    countries_analyzed: int
    categories_covered: int
    linked_to_profiles: int