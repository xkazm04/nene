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
    profile_id: Optional[str] = None  # Add profile_id support

class ExpertOpinion(BaseModel):
    critic: Optional[str] = None
    devil: Optional[str] = None
    nerd: Optional[str] = None
    psychic: Optional[str] = None

class ExpertPerspective(BaseModel):
    """Individual expert perspective for detailed analysis"""
    expert_name: str
    credentials: str
    stance: Literal["SUPPORTING", "OPPOSING", "NEUTRAL"]
    reasoning: str
    confidence_level: float  # 0-100
    source_type: Optional[Literal["llm", "web", "resource"]] = "llm"
    expertise_area: Optional[str] = None
    publication_date: Optional[str] = None

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

class ResearchMetadata(BaseModel):
    """Metadata about research sources and methods used"""
    research_sources: List[Literal["llm_training_data", "web_search", "resource_analysis"]]
    research_timestamp: str
    tri_factor_research: bool = False
    web_results_count: Optional[int] = None
    web_recency_score: Optional[float] = None
    total_resources_analyzed: Optional[int] = None
    resource_quality_score: Optional[float] = None
    processing_time_seconds: Optional[float] = None

class LLMResearchResponse(BaseModel):
    # Core fields (backward compatible)
    valid_sources: str  # e.g., "15 (85% agreement across 23 unique sources)"
    verdict: str # Final statement with 1-2 sentence summary
    status: Literal["TRUE", "FALSE", "MISLEADING", "PARTIALLY_TRUE", "UNVERIFIABLE"]
    correction: Optional[str] = None  # Corrected statement if original is false/misleading
    country: Optional[str] = None  # ISO country code of speaker/statement origin
    category: Optional[StatementCategory] = None  # Statement category
    resources_agreed: Optional[ResourceAnalysis] = None  # Make optional
    resources_disagreed: Optional[ResourceAnalysis] = None  # Make optional
    experts: Optional[ExpertOpinion] = None  # Make optional
    research_method: str  # Track which service was used
    profile_id: Optional[str] = None  # Add profile_id support
    
    # Enhanced fields for tri-factor research
    expert_perspectives: List[ExpertPerspective] = []  # Detailed expert perspectives
    key_findings: List[str] = []  # Key research findings
    research_summary: str = ""  # Comprehensive research summary
    additional_context: str = ""  # Additional context and metadata
    confidence_score: int = 50  # Overall confidence score (0-100)
    research_metadata: Optional[ResearchMetadata] = None  # Research process metadata
    
    # Source attribution
    llm_findings: List[str] = []  # Findings from LLM research
    web_findings: List[str] = []  # Findings from web search
    resource_findings: List[str] = []  # Findings from resource analysis

class TriFactorResearchResult(BaseModel):
    """Complete result from tri-factor research system"""
    statement: str
    original_request: LLMResearchRequest
    final_response: LLMResearchResponse
    
    # Individual research results
    llm_research: Optional[LLMResearchResponse] = None
    web_research: Optional[dict] = None
    resource_analysis: Optional[dict] = None
    
    # Processing metadata
    total_processing_time: float
    research_sources_used: List[str]
    fallback_reasons: List[str] = []  # Reasons why certain sources failed
    
    # Quality indicators
    overall_confidence: int  # 0-100
    source_consensus: float  # Agreement between sources (0-1)
    recency_score: float  # How recent the information is (0-100)
    authority_score: float  # Authority of sources (0-100)

# Helper functions for model conversion
def convert_expert_opinion_to_perspectives(expert_opinion: ExpertOpinion) -> List[ExpertPerspective]:
    """Convert old ExpertOpinion format to new ExpertPerspective list"""
    perspectives = []
    
    if expert_opinion.critic:
        perspectives.append(ExpertPerspective(
            expert_name="Critical Analyst",
            credentials="Expert in Critical Analysis",
            stance="NEUTRAL",
            reasoning=expert_opinion.critic,
            confidence_level=75.0,
            source_type="llm",
            expertise_area="Critical Analysis"
        ))
    
    if expert_opinion.devil:
        perspectives.append(ExpertPerspective(
            expert_name="Devil's Advocate",
            credentials="Expert in Counter-Arguments",
            stance="OPPOSING",
            reasoning=expert_opinion.devil,
            confidence_level=70.0,
            source_type="llm",
            expertise_area="Counter-Analysis"
        ))
    
    if expert_opinion.nerd:
        perspectives.append(ExpertPerspective(
            expert_name="Technical Expert",
            credentials="Technical/Scientific Expert",
            stance="NEUTRAL",
            reasoning=expert_opinion.nerd,
            confidence_level=85.0,
            source_type="llm",
            expertise_area="Technical Analysis"
        ))
    
    if expert_opinion.psychic:
        perspectives.append(ExpertPerspective(
            expert_name="Predictive Analyst",
            credentials="Expert in Future Implications",
            stance="NEUTRAL",
            reasoning=expert_opinion.psychic,
            confidence_level=60.0,
            source_type="llm",
            expertise_area="Predictive Analysis"
        ))
    
    return perspectives

def create_research_metadata(
    sources_used: List[str],
    web_count: Optional[int] = None,
    web_recency: Optional[float] = None,
    resource_count: Optional[int] = None,
    resource_quality: Optional[float] = None,
    processing_time: Optional[float] = None
) -> ResearchMetadata:
    """Create research metadata object"""
    from datetime import datetime
    
    return ResearchMetadata(
        research_sources=sources_used,
        research_timestamp=datetime.now().isoformat(),
        tri_factor_research=len(sources_used) > 1,
        web_results_count=web_count,
        web_recency_score=web_recency,
        total_resources_analyzed=resource_count,
        resource_quality_score=resource_quality,
        processing_time_seconds=processing_time
    )