from typing import List, Literal, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, validator

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
    stance: Literal["SUPPORTING", "OPPOSING", "NEUTRAL"]
    reasoning: str
    confidence_level: float  # 0-100
    summary: str  # One sentence summary of perspective
    source_type: Optional[Literal["llm", "web", "resource"]] = "llm"
    expertise_area: Optional[str] = None
    publication_date: Optional[str] = None

class ResourceReference(BaseModel):
    """Enhanced resource reference with flexible category system"""
    url: str
    title: str
    category: str = Field(..., description="Source category (flexible)")  # Made flexible instead of Literal
    country: str = Field(default="unknown", description="ISO country code")
    credibility: Literal["high", "medium", "low"] = Field(default="medium")
    domain: Optional[str] = Field(default=None, description="Source domain extracted from URL")
    key_finding: Optional[str] = Field(default=None, description="Key finding from this source")
    
    @validator('category')
    def normalize_category(cls, v):
        """Normalize category to standard values while allowing flexibility"""
        if not v:
            return "other"
        
        # Convert to lowercase for comparison
        v_lower = str(v).lower().strip()
        
        # Map common variations to standard categories
        category_mapping = {
            # Government/Official
            'government': 'governance',
            'gov': 'governance',
            'official': 'governance',
            'governmental': 'governance',
            'federal': 'governance',
            'state': 'governance',
            'municipal': 'governance',
            'public': 'governance',
            
            # News/Media
            'news': 'mainstream',
            'media': 'mainstream',
            'journalism': 'mainstream',
            'newspaper': 'mainstream',
            'broadcast': 'mainstream',
            'press': 'mainstream',
            
            # Academic/Research
            'university': 'academic',
            'research': 'academic',
            'scientific': 'academic',
            'scholarly': 'academic',
            'education': 'academic',
            'institute': 'academic',
            'college': 'academic',
            
            # Medical/Health
            'health': 'medical',
            'healthcare': 'medical',
            'hospital': 'medical',
            'clinic': 'medical',
            'pharmaceutical': 'medical',
            
            # Economic/Financial
            'economic': 'economic',
            'financial': 'economic',
            'finance': 'economic',
            'banking': 'economic',
            'investment': 'economic',
            'business': 'economic',
            'commercial': 'economic',
            'corporate': 'economic',
            
            # Legal
            'legal': 'legal',
            'law': 'legal',
            'court': 'legal',
            'judicial': 'legal',
            'attorney': 'legal',
            
            # Technology
            'tech': 'technology',
            'technological': 'technology',
            'digital': 'technology',
            'software': 'technology',
            'computer': 'technology',
            
            # International/Global
            'international': 'international',
            'global': 'international',
            'world': 'international',
            'multilateral': 'international',
            
            # Think tanks/Policy
            'think_tank': 'policy',
            'thinktank': 'policy',
            'policy': 'policy',
            'advocacy': 'policy',
            
            # Fact-checking
            'fact_check': 'fact_checking',
            'factcheck': 'fact_checking',
            'verification': 'fact_checking',
        }
        
        # Return mapped category or original if not found
        return category_mapping.get(v_lower, v_lower)
    
    @validator('country')
    def normalize_country(cls, v):
        """Normalize country codes"""
        if not v or v.lower() in ['unknown', 'null', 'none']:
            return "unknown"
        
        # Common country code mappings
        country_mapping = {
            'usa': 'us',
            'united states': 'us',
            'america': 'us',
            'uk': 'gb',
            'britain': 'gb',
            'england': 'gb',
            'united kingdom': 'gb',
            'germany': 'de',
            'deutschland': 'de',
            'france': 'fr',
            'canada': 'ca',
            'australia': 'au',
            'japan': 'jp',
            'china': 'cn',
            'india': 'in',
            'brazil': 'br',
            'russia': 'ru',
            'italy': 'it',
            'spain': 'es',
            'netherlands': 'nl',
            'switzerland': 'ch',
            'sweden': 'se',
            'norway': 'no',
            'denmark': 'dk',
            'finland': 'fi',
        }
        
        v_lower = str(v).lower().strip()
        return country_mapping.get(v_lower, v_lower[:2])  # Default to first 2 chars

class ResourceAnalysis(BaseModel):
    """Enhanced resource analysis with flexible categorization"""
    total: str = Field(default="0%", description="Total percentage agreement")
    count: int = Field(default=0, description="Total number of sources")
    
    # Traditional categories (maintain backward compatibility)
    mainstream: int = Field(default=0, description="Major news outlets")
    governance: int = Field(default=0, description="Government sources")
    academic: int = Field(default=0, description="Academic/research sources")
    medical: int = Field(default=0, description="Medical/health sources")
    other: int = Field(default=0, description="Other sources")
    
    # Extended categories (new)
    economic: int = Field(default=0, description="Economic/financial sources")
    legal: int = Field(default=0, description="Legal sources")
    technology: int = Field(default=0, description="Technology sources")
    international: int = Field(default=0, description="International organization sources")
    policy: int = Field(default=0, description="Think tanks and policy sources")
    fact_checking: int = Field(default=0, description="Fact-checking organizations")
    
    major_countries: List[str] = Field(default_factory=list, description="Major countries represented")
    references: List[ResourceReference] = Field(default_factory=list, description="Source references")
    
    @validator('total')
    def format_total_percentage(cls, v):
        """Ensure total is properly formatted as percentage"""
        if not v or v == "null":
            return "0%"
        if isinstance(v, (int, float)):
            return f"{v}%"
        if not str(v).endswith('%'):
            return f"{v}%"
        return str(v)

class ResearchMetadata(BaseModel):
    """Metadata about research sources and methods used"""
    research_sources: List[Literal["llm_training_data", "web_search", "resource_analysis"]]
    research_timestamp: str
    tri_factor_research: bool = False
    web_results_count: Optional[int] = None
    web_recency_score: Optional[float] = None
    total_resources_analyzed: Optional[int] = None
    resource_quality_score: Optional[float] = None

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

# Helper functions for model conversion
def convert_expert_opinion_to_perspectives(expert_opinion: ExpertOpinion) -> List[ExpertPerspective]:
    """Convert old ExpertOpinion format to new ExpertPerspective list"""
    perspectives = []
    
    if expert_opinion.critic:
        perspectives.append(ExpertPerspective(
            expert_name="Critical Analyst",
            stance="NEUTRAL",
            reasoning=expert_opinion.critic,
            summary="Critical analysis perspective",
            confidence_level=75.0,
            source_type="llm",
            expertise_area="Critical Analysis"
        ))
    
    if expert_opinion.devil:
        perspectives.append(ExpertPerspective(
            expert_name="Devil's Advocate",
            stance="OPPOSING",
            reasoning=expert_opinion.devil,
            summary="Counter-argument perspective",
            confidence_level=70.0,
            source_type="llm",
            expertise_area="Counter-Analysis"
        ))
    
    if expert_opinion.nerd:
        perspectives.append(ExpertPerspective(
            expert_name="Technical Expert",
            stance="NEUTRAL",
            reasoning=expert_opinion.nerd,
            summary="Technical analysis perspective",
            confidence_level=85.0,
            source_type="llm",
            expertise_area="Technical Analysis"
        ))
    
    if expert_opinion.psychic:
        perspectives.append(ExpertPerspective(
            expert_name="Predictive Analyst",
            stance="NEUTRAL",
            reasoning=expert_opinion.psychic,
            summary="Future implications perspective",
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
    )