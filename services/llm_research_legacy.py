# Legacy import support - redirect to new structure
from services.llm_research import llm_research_service
from models.research_models import (
    LLMResearchRequest,
    LLMResearchResponse,
    ExpertOpinion,
    ResourceAnalysis,
    ResourceReference,
    StatementCategory
)

# Export everything for backwards compatibility
__all__ = [
    'llm_research_service',
    'LLMResearchRequest',
    'LLMResearchResponse', 
    'ExpertOpinion',
    'ResourceAnalysis',
    'ResourceReference',
    'StatementCategory'
]