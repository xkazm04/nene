from typing import List, Literal, Optional
from enum import Enum
from pydantic import BaseModel

class StatementCategory(str, Enum):
    """Categories for statement classification."""
    POLITICS = "politics"
    ECONOMY = "economy"
    ENVIRONMENT = "environment"
    MILITARY = "military"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    TECHNOLOGY = "technology"
    SOCIAL = "social"
    INTERNATIONAL = "international"
    OTHER = "other"

class LLMResearchRequest(BaseModel):
    statement: str
    source: str
    context: str
    country: Optional[str] = None  # ISO country code (e.g., "us", "gb", "de")
    category: Optional[StatementCategory] = None

class ExpertOpinion(BaseModel):
    critic: Optional[str] = None
    devil: Optional[str] = None
    nerd: Optional[str] = None
    psychic: Optional[str] = None

class ResourceReference(BaseModel):
    url: str
    title: str
    category: Literal["mainstream", "governance", "academic", "medical", "other"]
    country: str
    credibility: Literal["high", "medium", "low"]

class ResourceAnalysis(BaseModel):
    total: str  # e.g., "85%"
    count: int
    mainstream: int = 0
    governance: int = 0
    academic: int = 0
    medical: int = 0
    other: int = 0
    major_countries: List[str] = []
    references: List[ResourceReference] = []

class LLMResearchResponse(BaseModel):
    valid_sources: str  # e.g., "15 (85% agreement across 23 unique sources)"
    verdict: str
    status: Literal["TRUE", "FALSE", "MISLEADING", "PARTIALLY_TRUE", "UNVERIFIABLE"]
    correction: Optional[str] = None  # Corrected statement if original is false/misleading
    country: Optional[str] = None  # ISO country code of speaker/statement origin
    category: Optional[StatementCategory] = None  # Statement category
    resources_agreed: Optional[ResourceAnalysis] = None  # Make optional
    resources_disagreed: Optional[ResourceAnalysis] = None  # Make optional
    experts: Optional[ExpertOpinion] = None  # Make optional
    research_method: str  # Track which service was used